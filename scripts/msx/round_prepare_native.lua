-- Isolated original $08bf..$08d4 prefix, with exact execution-boundary snapshots.
local m = manager.machine
local cpu = m.devices[':maincpu']
local s = cpu.spaces['program']
local config = dofile(assert(os.getenv('ROUND_PREPARE_CONFIG')))
local function read(path)
    local f = io.open(path, 'rb')
    if not f then return nil end
    local data = f:read('a'); f:close(); return data
end
local seed = assert(read(config.output..'/source-seed.bin'))
local result = assert(io.open(config.output..'/original.bin', 'wb'))
local current = config.output..'/current.bin'
local frame, index, issued = 0, 0, 0
local function issue()
    index = index + 1
    if index > #config.cases then
        result:close()
        local f = assert(io.open(config.output..'/complete', 'w'))
        f:write('ok\n'); f:close(); m:exit(); return
    end
    os.remove(current)
    for i = 1, #seed do s:write_u8(0x8000+i-1, seed:byte(i)) end
    local case = config.cases[index]
    s:write_u8(0x81b0, case[1]-1)
    s:write_u8(0x8000, case[2]); s:write_u8(0x8001, case[3])
    s:write_u8(0x8292, 0)
    -- DI; CALL original preparation; HALT. The breakpoint captures before
    -- original hardware writes rather than patching the original ROM.
    for i, value in ipairs({0xf3,0xcd,0xbf,0x08,0x76}) do s:write_u8(0x9f80+i-1, value) end
    cpu.state.HALT.value = 0
    cpu.state.IFF1.value = 0; cpu.state.IFF2.value = 0
    cpu.state.SP.value = 0x9ff0; cpu.state.PC.value = 0x9f80
    cpu.debug:bpclear()
    cpu.debug:bpset(0x08d4, '1', 'save '..string.format('%q', current)..',8000,1000;bpdisable;g')
    m.debugger.execution_state = 'run'; issued = frame
end
m.debugger.execution_state = 'run'
emu.register_frame_done(function()
    frame = frame + 1; s:write_u8(0xa080, 0)
    if frame == 10 then issue(); return end
    if index == 0 then return end
    local data = read(current)
    if data then
        assert(#data == 4096, 'Incomplete original preparation snapshot')
        result:write(data); issue()
    elseif frame-issued > 120 then
        print(string.format('Original preparation timeout case=%d PC=%04x', index, cpu.state.PC.value))
        result:close(); m:exit()
    end
end)
