-- Real gameplay only. Install observation taps, reset, replay inputs and capture.
if _G.nrallyx_capture_started then return end
_G.nrallyx_capture_started = true
local config = dofile(assert(os.getenv('NRALLYX_CAPTURE_CONFIG')))
local machine = manager.machine
local screen = machine.screens[':screen']
local space = machine.devices[':maincpu'].spaces['program']
local registers, taps, frame, generation = {}, {}, 0, 0
local history = {}
local installing = false
local map_subscription = space:add_change_notifier(function(mode)
    if not installing and mode:find('w',1,true) then
        -- MAME can deliver installation notifications after the reset callback.
        -- Discard all cached values; only fresh observed writes may initialize them.
        registers = {}
    end
end)
local fields = {}
for _,port in pairs(machine.ioport.ports) do
    for _,field in pairs(port.fields) do fields[field.name] = field end
end
for _,event in ipairs(config.inputs) do assert(fields[event.field], 'Unknown input '..event.field) end
local function write(path, data)
    local f = assert(io.open(path, 'wb')); f:write(data); f:close()
end
local function bytes(share, size)
    assert(share and share.size == size, 'Unexpected memory share')
    local data = {}
    for offset=0,size-1 do data[#data+1]=string.char(share:read_u8(offset)) end
    return table.concat(data)
end
local function install()
    installing = true
    for _,tap in ipairs(taps) do tap:remove() end
    taps = {}
    for _,entry in ipairs({{0xa130,'scroll_x'},{0xa140,'scroll_y'},{0xa183,'flip'}}) do
        local address,key = entry[1],entry[2]
        taps[#taps+1] = space:install_write_tap(address,address,'capture_'..key,
            function(_,data,_) registers[key] = key=='flip' and (data & 1) or data end)
    end
    installing = false
end
local reset_subscription = emu.add_machine_reset_notifier(function()
    registers = {}; frame = 0; generation = generation+1
    install()
end)
install()
machine:soft_reset()
local next_event, next_capture = 1, 1
local function on_frame()
    if generation == 0 then return end
    assert(map_subscription and reset_subscription, 'Lost lifecycle subscription')
    assert(generation == 1, 'Unexpected machine reset invalidates replay')
    frame = frame+1
    -- screen_device::vblank_begin -> frame_update -> finish_screen_updates ->
    -- frame_hook (here), then screen_vblank raises IRQ. CPU cannot run between.
    if frame == config.frames[next_capture] then
        assert(registers.scroll_x and registers.scroll_y and registers.flip,
            'Uninitialized video register after reset')
        local dest = config.destination..string.format('/frame-%05d',frame)
        write(dest..'/video.bin',bytes(machine.memory.shares[':videoram'],4096))
        write(dest..'/radar-attributes.bin',bytes(machine.memory.shares[':radarattr'],16))
        assert(emu.app_version() == '0.289','Unsupported MAME version')
        local state = config.header..string.format(
            ',"state_frame":%d,"bitmap_frame":%d,"emulated_time":"%s",'..
            '"reset_generation":%d,"registers":{"scroll_x":%d,"scroll_y":%d,"flip":%d},'..
            '"initialized":true,"replay_frame":%d,"inputs":[%s]}',
            screen:frame_number(),screen:frame_number(),tostring(machine.time),
            generation,registers.scroll_x,registers.scroll_y,registers.flip,frame,table.concat(history,','))
        write(dest..'/capture.json',state)
        assert(screen:snapshot(dest..'/reference.png') == nil, 'Native snapshot failed')
        write(dest..'/complete','ok')
        next_capture=next_capture+1
        if next_capture > #config.frames then machine:exit() end
    end
    while config.inputs[next_event] and config.inputs[next_event].frame == frame do
        local event = config.inputs[next_event]
        fields[event.field]:set_value(event.value)
        history[#history+1]=string.format('{"frame":%d,"field":%q,"value":%d}',frame,event.field,event.value)
        next_event=next_event+1
    end
end
emu.register_frame_done(function()
    local ok,err=pcall(on_frame)
    if not ok then
        write(config.destination..'/failure.txt',tostring(err))
        print('CAPTURE FAILED: '..tostring(err))
        machine:exit()
    end
end)
