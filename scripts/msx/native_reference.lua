-- Observe a fresh, unmodified arcade reset and exact game-IRQ boundaries.
if _G.nrallyx_native_reference then return end
_G.nrallyx_native_reference = true
local config = dofile(assert(os.getenv('NRALLYX_NATIVE_REFERENCE')))
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local space = cpu.spaces['program']
local debugger = assert(machine.debugger)
local frame, generation, tick, next_input = 0, 0, 0, 1
local ready, boot_frame, foreground = false, -1, false
local pending, transfer = false, false
local shadows, taps, breakpoints = {}, {}, {}
local tile_writers = {}
local events = assert(io.open(config.output..'/boundaries.tsv','w'))
local inputs = assert(io.open(config.output..'/inputs.tsv','w'))
local masks = assert(io.open(config.output..'/masks.tsv','w'))
local registers = assert(io.open(config.output..'/registers.tsv','w'))
local register_names = {'AF','BC','DE','HL','IX','IY','AF2','BC2','DE2','HL2'}
registers:write('tick\tphase\t'..table.concat(register_names,'\t')..'\n')
masks:write('tick\tframe\tpc\tvalue\tbusy\ttime\n')
inputs:write('tick\tframe\tp1\tp2\tdip\n')
events:write('tick\tframe\tphase\tpc\tsp\tim\ti\tiff1\ttime\n')
local function write(name, data)
    local file = assert(io.open(config.output..'/'..name,'wb'))
    file:write(data); file:close()
end
local function snapshot(name)
    local bytes = {}
    for a=0x8000,0x8fff do bytes[#bytes+1]=string.char(space:read_u8(a)) end
    for a=0x9800,0x9fff do bytes[#bytes+1]=string.char(space:read_u8(a)) end
    for a=0xa000,0xa187 do bytes[#bytes+1]=string.char(shadows[a] or 0) end
    write(name,table.concat(bytes))
end
local function boundary(phase)
    events:write(string.format('%d\t%d\t%s\t%04x\t%04x\t%d\t%02x\t%d\t%s\n',
        tick,frame,phase,cpu.state.PC.value,cpu.state.SP.value,cpu.state.IM.value,
        cpu.state.I.value,cpu.state.IFF1.value,tostring(machine.time)))
    if tick<=1 or phase=='foreground-entry' then
        local row = {tostring(tick),phase}
        for _,name in ipairs(register_names) do row[#row+1]=string.format('%04x',cpu.state[name].value) end
        registers:write(table.concat(row,'\t')..'\n')
    end
end
local fields = {}
for _,port in pairs(machine.ioport.ports) do
    for _,field in pairs(port.fields) do fields[field.name] = field end
end
local function install()
    for _,tap in ipairs(taps) do tap:remove() end
    taps = {}
    taps[#taps+1] = space:install_write_tap(0x8000,0x8fff,'native_video_writers',function(a,data)
        if generation==1 and not machine:side_effects_disabled() then
            local pc=cpu.state.PC.value
            local row=tile_writers[pc] or {count=0,first=a,last=a}
            row.count=row.count+1; row.first=math.min(row.first,a); row.last=math.max(row.last,a)
            tile_writers[pc]=row
        end
    end)
    taps[#taps+1] = space:install_write_tap(0xa000,0xa1ff,'native_shadows',function(a,data)
        if generation==1 and not machine:side_effects_disabled() then shadows[a]=data end
        if generation==1 and ready and a==0xa181 and not machine:side_effects_disabled() then
            masks:write(string.format('%d\t%d\t%d\t%d\t%d\t%s\n',tick,frame,
                cpu.state.PC.value,data,pending and 1 or 0,tostring(machine.time)))
        end
    end)
    taps[#taps+1] = space:install_read_tap(3,3,'native_initialization',function(a,data)
        if generation==1 and not ready and not machine:side_effects_disabled() and cpu.state.PC.value==3 then
            ready=true; boot_frame=frame
            snapshot('initialization.bin'); boundary('initialization-entry')
            -- Memory taps also see operand/data reads. Only execution
            -- breakpoints can establish whether an EI/DI byte is code.
            for _,site in ipairs(config.control_sites) do
                breakpoints[#breakpoints+1] = cpu.debug:bpset(site.address,'1',
                    'logerror "NATIVE_CONTROL %04X\\n",pc;g')
            end
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x01f0,0x01f0,'native_game_entry',function(a,data)
        if generation==1 and ready and not machine:side_effects_disabled() and cpu.state.PC.value==0x01f0 then
            assert(not pending,'Unclassified nonreturning IRQ')
            pending=true; boundary('pre-game-irq')
            inputs:write(string.format('%d\t%d\t%02x\t%02x\t%02x\n',tick,frame,
                space:read_u8(0xa000),space:read_u8(0xa080),space:read_u8(0xa100)))
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x0c2c,0x0c2c,'native_foreground',function(a,data)
        if generation==1 and ready and not foreground and not machine:side_effects_disabled() and cpu.state.PC.value==0x0c2c then
            foreground=true; snapshot('foreground-entry.bin'); boundary('foreground-entry')
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x0471,0x0471,'native_game_exit',function(a,data)
        if generation==1 and ready and not machine:side_effects_disabled() and cpu.state.PC.value==0x0471 then
            assert(pending and not transfer,'Unexpected IRQ return')
            pending=false
            tick=tick+1; boundary('post-game-irq')
            snapshot(string.format('state-%05d.bin',tick))
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x075a,0x075a,'native_irq_transfer',function(a,data)
        if generation==1 and ready and pending and not machine:side_effects_disabled() and cpu.state.PC.value==0x075a then
            transfer=1; boundary('game-irq-transfer')
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x0769,0x0769,'native_irq_transfer_end',function(a,data)
        if generation==1 and ready and transfer==1 and not machine:side_effects_disabled() and cpu.state.PC.value==0x0769 then
            assert(pending,'Unexpected IRQ transfer publication')
            transfer=false; pending=false; tick=tick+1
            boundary('post-game-irq-transfer'); snapshot(string.format('state-%05d.bin',tick))
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x03b9,0x03b9,'native_collision_transfer',function(a,data)
        if generation==1 and ready and pending and not machine:side_effects_disabled() and cpu.state.PC.value==0x03b9 then
            assert(not transfer,'Nested collision transfer')
            transfer=2; boundary('game-irq-collision')
        end
    end)
    taps[#taps+1] = space:install_read_tap(0x18c1,0x18c1,'native_collision_publication',function(a,data)
        if generation==1 and ready and transfer==2 and not machine:side_effects_disabled() and cpu.state.PC.value==0x18c1 then
            assert(pending,'Unexpected collision publication')
            transfer=false; pending=false; tick=tick+1
            boundary('post-game-irq-collision'); snapshot(string.format('state-%05d.bin',tick))
        end
    end)
end
local reset_subscription = emu.add_machine_reset_notifier(function()
    generation=generation+1; assert(generation==1,'Unexpected reset')
    frame=0; tick=0; ready=false; foreground=false; pending=false; transfer=false; shadows={}; install()
    debugger:command('trace '..string.format('%q',config.output..'/execution.trace')..',:maincpu')
    debugger.execution_state='run'
end)
install()
machine:soft_reset()
debugger.execution_state='run'
emu.register_frame_done(function()
    if generation~=1 then return end
    assert(reset_subscription)
    frame=frame+1
    while config.inputs[next_input] and config.inputs[next_input].frame==frame do
        local event=config.inputs[next_input]
        assert(fields[event.field],'Unknown input field'):set_value(event.value)
        next_input=next_input+1
    end
    if frame==config.frames then
        assert(next_input>#config.inputs,'Replay contains unapplied events')
        debugger:command('trace off')
        events:close(); inputs:close(); masks:close(); registers:close()
        local writers=assert(io.open(config.output..'/video-writers.tsv','w'))
        writers:write('pc\tcount\tfirst\tlast\n')
        local addresses={}
        for pc,_ in pairs(tile_writers) do addresses[#addresses+1]=pc end
        table.sort(addresses)
        for _,pc in ipairs(addresses) do
            local row=tile_writers[pc]
            writers:write(string.format('%04x\t%d\t%04x\t%04x\n',pc,row.count,row.first,row.last))
        end
        writers:close()
        write('execution.json',string.format('{"schema_version":1,"boot_frame":%d,"ticks":%d}\n',boot_frame,tick))
        write('complete',ready and tick>0 and 'ok\n' or 'missing-boundary\n')
        machine:exit()
    end
end)
