-- Observe unmodified contributor code after a fresh soft reset. No ROM patches.
if _G.nrallyx_analysis_started then return end
_G.nrallyx_analysis_started = true
local config = dofile(assert(os.getenv('NRALLYX_ANALYSIS_CONFIG')))
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local space, iospace = cpu.spaces['program'], cpu.spaces['io']
local debugger = assert(machine.debugger, 'Enable debugger')
local frame, generation, next_event = 0, 0, 1
local taps, counts, shadows = {}, {}, {}
local events = assert(io.open(config.destination..'/accesses.tsv','w'))
events:write('frame\tspace\tdirection\tpc_reported\taddress\tvalue\tcount\n')
local states = assert(io.open(config.destination..'/frames.tsv','w'))
states:write('frame\tpc\tsp\tim\ti\tiff1\ttime\n')
local fields = {}
for _,port in pairs(machine.ioport.ports) do
    for _,field in pairs(port.fields) do fields[field.name] = field end
end
local function observe(kind, direction)
    return function(address, data, mask)
        if generation ~= 1 then return end
        local pc = cpu.state['PC'].value
        local key = string.format('%s\t%s\t%04x\t%04x\t%02x', kind,direction,pc,address,data)
        counts[key] = (counts[key] or 0)+1
        if kind=='program' and direction=='w' and address>=0xa000 then shadows[address]=data end
    end
end
local function install()
    for _,tap in ipairs(taps) do tap:remove() end
    taps = {
        space:install_write_tap(0,0xffff,'analysis_writes',observe('program','w')),
        space:install_read_tap(0xa000,0xffff,'analysis_inputs',observe('program','r')),
        iospace:install_write_tap(0,0xff,'analysis_io_w',observe('io','w')),
        iospace:install_read_tap(0,0xff,'analysis_io_r',observe('io','r'))
    }
end
local reset_subscription = emu.add_machine_reset_notifier(function()
    generation=generation+1; assert(generation==1,'Unexpected reset')
    frame=0; counts={}; shadows={}; install()
    debugger:command('trace '..string.format('%q',config.destination..'/reset.trace')..',:maincpu,noloop')
    debugger.execution_state='run'
end)
install()
machine:soft_reset()
debugger.execution_state='run'
local function write(path, data)
    local file=assert(io.open(config.destination..'/'..path,'wb'));file:write(data);file:close()
end
local function snapshot()
    local bytes={}
    for a=0x8000,0x8fff do bytes[#bytes+1]=string.char(space:read_u8(a)) end
    for a=0x9800,0x9fff do bytes[#bytes+1]=string.char(space:read_u8(a)) end
    for a=0xa000,0xa187 do bytes[#bytes+1]=string.char(shadows[a] or 0) end
    write(string.format('state-%05d.bin',frame),table.concat(bytes))
end
emu.register_frame_done(function()
    if generation==0 then return end
    assert(reset_subscription and generation==1)
    frame=frame+1
    local keys={};for key,_ in pairs(counts) do keys[#keys+1]=key end;table.sort(keys)
    for _,key in ipairs(keys) do events:write(frame..'\t'..key..'\t'..counts[key]..'\n') end
    counts={}
    states:write(string.format('%d\t%04x\t%04x\t%d\t%02x\t%d\t%s\n',frame,
        cpu.state['PC'].value,cpu.state['SP'].value,cpu.state['IM'].value,
        cpu.state['I'].value,cpu.state['IFF1'].value,tostring(machine.time)))
    -- Same vblank-before-IRQ sampling and input phase as scenes/capture.lua.
    if frame==2 or frame==658 or frame==760 or frame==1017 or frame==1862 or frame==2302 or frame==2402 then debugger:command('trace off') end
    if frame==654 or frame==756 or frame==1015 or frame==1860 or frame==2300 or frame==2400 then
        debugger:command('trace '..string.format('%q',config.destination..'/frame-'..frame..'.trace')..',:maincpu,noloop')
    end
    if frame>=1799 then snapshot() end
    while config.inputs[next_event] and config.inputs[next_event].frame==frame do
        local event=config.inputs[next_event]
        assert(fields[event.field],'Unknown replay field'):set_value(event.value)
        next_event=next_event+1
    end
    if frame==config.frames then
        debugger:command('trace off'); events:close();states:close()
        write('complete','ok\n');machine:exit()
    end
end)
