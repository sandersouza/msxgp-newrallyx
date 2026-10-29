-- Observe the unmodified arcade through real inputs. Never write guest RAM/ROM.
local m = manager.machine
local cpu = m.devices[':maincpu']
local s = cpu.spaces['program']
local out = assert(os.getenv('AUDIO_INVENTORY_OUTPUT'))
local limit = assert(tonumber(os.getenv('AUDIO_INVENTORY_FRAMES')))
local frames = assert(io.open(out..'/frames.tsv', 'w'))
local writes = assert(io.open(out..'/writes.tsv', 'w'))
local inputs = assert(io.open(out..'/inputs.tsv', 'w'))
local fields = {}
for _, field in pairs(m.ioport.ports[':P1'].fields) do fields[field.mask] = field end
assert(fields[0x80] and fields[0x40] and fields[0x02], 'Missing coin/start/smoke fields')
local shadow = {}
for i = 0, 31 do shadow[i] = 0 end
local taps, frame, count = {}, 0, 0
local ready = false
local sequencer = os.getenv('AUDIO_INVENTORY_SEQUENCER') == '1'
local cases, hardware, stack, active, case, original_sp = nil, nil, nil, false, 0, 0
if sequencer then
    cases = assert(io.open(out..'/sequencer.bin', 'wb'))
    hardware = assert(io.open(out..'/sequencer-writes.tsv', 'w'))
    stack = assert(io.open(out..'/sequencer-stack.tsv', 'w'))
end
local function snapshot()
    local bytes = {}
    for at = 0x8000, 0x8bff do bytes[#bytes+1] = string.char(s:read_u8(at)) end
    for i = 0, 31 do bytes[#bytes+1] = string.char(shadow[i]) end
    cases:write(table.concat(bytes))
end
local function observe(address, value)
    if m:side_effects_disabled() then return end
    count = count + 1
    assert(count <= 2000000, 'Sound trace event budget exceeded')
    writes:write(string.format('%d %d %d %d %s\n', frame,
        cpu.state.PC.value, address, value, tostring(m.time)))
    if active and address >= 0xa100 then
        hardware:write(string.format('%d %d %d\n', case, address, value))
    end
end
taps[#taps+1] = s:install_write_tap(0xa100, 0xa11f, 'audio_wsg', function(a, value)
    if not m:side_effects_disabled() then shadow[a-0xa100] = value & 15 end
    observe(a, value)
end)
if sequencer then
    taps[#taps+1] = s:install_read_tap(0x2580, 0x2580, 'audio_entry', function(a, value)
        if ready and not m:side_effects_disabled() and cpu.state.PC.value == 0x2580 then
            assert(not active, 'Nested sound sequencer call')
            case = case + 1; active = true; original_sp = cpu.state.SP.value; snapshot()
        end
    end)
    taps[#taps+1] = s:install_write_tap(0x8000, 0x89ff, 'audio_original_stack', function(a, value)
        if active and not m:side_effects_disabled() and not (a >= 0x89f4 and a <= 0x89f6) then
            assert(a >= original_sp-64 and a < original_sp, 'Unexpected sequencer game-state write')
            stack:write(string.format('%d %d\n', case, a))
        end
    end)
    taps[#taps+1] = s:install_read_tap(0x2a01, 0x2a01, 'audio_return', function(a, value)
        if active and not m:side_effects_disabled() and cpu.state.PC.value == 0x2a01 then
            snapshot(); active = false
        end
    end)
end
taps[#taps+1] = s:install_write_tap(0x89f4, 0x89f6, 'audio_requests', observe)
taps[#taps+1] = s:install_write_tap(0xa180, 0xa180, 'audio_bang', observe)
taps[#taps+1] = s:install_write_tap(0xa182, 0xa182, 'audio_enable', observe)
taps[#taps+1] = s:install_read_tap(3, 3, 'audio_boot_ready', function(a, value)
    if not ready and not m:side_effects_disabled() and cpu.state.PC.value == 3 then
        ready = true
        local f = assert(io.open(out..'/boot-ready', 'w'))
        f:write(frame..'\n'); f:close()
    end
end)
local function input(mask, down)
    fields[mask]:set_value(down)
    inputs:write(string.format('%d %d %d\n', frame, mask, down))
end
m.debugger.execution_state = 'run'
emu.register_frame_done(function()
    assert(#taps == (sequencer and 8 or 5)) -- Retain tap userdata across Lua GC.
    frame = frame + 1
    local row = {frame, s:read_u8(0x8020), s:read_u8(0x81b0),
        s:read_u8(0x8024), s:read_u8(0x800f), s:read_u8(0x8271),
        s:read_u8(0x89f4), s:read_u8(0x89f5), s:read_u8(0x89f6)}
    for i = 0, 31 do row[#row+1] = shadow[i] end
    frames:write(table.concat(row, ' ')..'\n')
    if frame == 1800 then input(0x80, 1) end
    if frame == 1804 then input(0x80, 0) end
    if frame == 1840 then input(0x40, 1) end
    if frame == 1844 then input(0x40, 0) end
    if frame >= 2000 then
        local phase = (frame-2000) % 180
        if phase == 0 and s:read_u8(0x8020) == 2 then input(0x02, 1) end
        if phase == 8 then input(0x02, 0) end
    end
    if frame >= limit then
        assert(not active, 'Capture ended during a sound sequencer call')
        frames:close(); writes:close(); inputs:close()
        if sequencer then
            cases:close(); hardware:close(); stack:close()
            local f = assert(io.open(out..'/sequencer-count', 'w'))
            f:write(case..'\n'); f:close()
        end
        local f = assert(io.open(out..'/complete', 'w'))
        f:write(frame..'\n'); f:close(); m:exit()
    end
end)
