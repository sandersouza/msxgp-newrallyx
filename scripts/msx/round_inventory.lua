-- Real credit/start followed by explicitly seeded original round initializers.
-- This is component acquisition, not a replay of naturally completed rounds.
local m = manager.machine
local cpu = m.devices[':maincpu']
local s = cpu.spaces['program']
local config = dofile(assert(os.getenv('ROUND_INVENTORY_CONFIG')))
local debugger = assert(m.debugger)
local fields = {}
for _, port in pairs(m.ioport.ports) do
    for _, field in pairs(port.fields) do fields[field.name] = field end
end
local frame, index, first_frame = 0, 0, 0
local active, initial = false, nil
local events = assert(io.open(config.output..'/events.tsv', 'w'))
events:write('case\tframe\tround_byte\tchallenge_intro\telapsed_frames\n')
local function path(suffix)
    return config.output..'/'..string.format('case-%03d-', index)..suffix
end
local function read(name)
    local f = io.open(name, 'rb')
    if not f then return nil end
    local data = f:read('a'); f:close(); return data
end
local function arm()
    cpu.debug:bpclear()
    cpu.debug:bpset(0x09d3, '1', 'save '..string.format('%q', path('challenge.bin'))..',81b0,1;g')
    local action = 'save '..string.format('%q', path('video.bin'))..',8000,1000;'
        ..'save '..string.format('%q', path('work.bin'))..',9800,800;'
        ..'bpdisable;g'
    -- The unmodified arcade's active single-player mode is 2; the selected
    -- MSX adapter deliberately uses 1. Do not conflate these state contracts.
    cpu.debug:bpset(0x0c2c, 'b@8020==2', action)
    first_frame = frame; active = true
    debugger.execution_state = 'run'
end
debugger.execution_state = 'run'
emu.register_frame_done(function()
    frame = frame + 1
    if frame == 1800 then fields['Coin 1']:set_value(1) end
    if frame == 1804 then fields['Coin 1']:set_value(0) end
    if frame == 1860 then
        arm(); fields['1 Player Start']:set_value(1)
        local f = assert(io.open(config.output..'/dip.bin', 'wb'))
        f:write(string.char(s:read_u8(0xa100))); f:close()
    end
    if frame == 1864 then fields['1 Player Start']:set_value(0) end
    if active then
        local video = read(path('video.bin'))
        local work = read(path('work.bin'))
        if video and work then
            assert(#video == 4096 and #work == 2048, 'Incomplete breakpoint snapshot')
            local expected = index == 0 and 2 or config.rounds[index]
            assert(video:byte(0x1b0+1) == expected, 'Unexpected source round byte')
            assert(video:byte(0x271+1) == 0, 'Source entered with collected flags')
            events:write(string.format('%d\t%d\t%d\t%d\t%d\n', index, frame,
                expected, read(path('challenge.bin')) and 1 or 0, frame-first_frame))
            initial = initial or video
            index = index + 1
            if index > #config.rounds then
                events:close()
                local f = assert(io.open(config.output..'/complete', 'w'))
                f:write('ok\n'); f:close(); m:exit(); return
            end
            -- Restore real first-game RAM, then let the original increment,
            -- dispatch, sound waits and preparation execute without ROM patches.
            for i = 1, #initial do s:write_u8(0x8000+i-1, initial:byte(i)) end
            s:write_u8(0x81b0, config.rounds[index]-1)
            s:write_u8(0x8000, config.random[1]); s:write_u8(0x8001, config.random[2])
            -- Post-completion entry requires the sound-ready bit, unlike the
            -- first-game snapshot's pending background-music request.
            s:write_u8(0x89f5, 1)
            cpu.state.HALT.value = 0
            cpu.state.SP.value = 0x8400; cpu.state.PC.value = 0x08bf
            cpu.state.IFF1.value = 1; cpu.state.IFF2.value = 1
            arm()
        end
    end
    if active and frame-first_frame >= 1800 then
        print(string.format('Round timeout case=%d PC=%04x SP=%04x mode=%d round=%d sound=%02x',
            index, cpu.state.PC.value, cpu.state.SP.value, s:read_u8(0x8020),
            s:read_u8(0x81b0), s:read_u8(0x89f5)))
        events:close(); m:exit()
    end
end)
