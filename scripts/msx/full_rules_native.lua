-- Original phase-clock prefix, captured before unrelated arcade IRQ output.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local config=dofile(assert(os.getenv('FULL_RULES_CONFIG')))
local function read(path)
    local f=io.open(path,'rb');if not f then return nil end
    local bytes=f:read('a');f:close();return bytes
end
local seed=assert(read(config.output..'/source-seed.bin'))
local result=assert(io.open(config.output..'/original.bin','wb'))
local current=config.output..'/current.bin'
local index,frame,issued=0,0,0
local function issue()
    index=index+1
    if index>#config.cases then
        result:close();local f=assert(io.open(config.output..'/complete','w'))
        f:write('ok\n');f:close();m:exit();return
    end
    os.remove(current)
    for i=1,#seed do s:write_u8(0x8000+i-1,seed:byte(i)) end
    local offsets={0x1b0,0x289,0x28c,0x271,0x292}
    for i,value in ipairs(config.cases[index]) do s:write_u8(0x8000+offsets[i],value) end
    for i,value in ipairs({0xf3,0xcd,0x1f,0x1b,0xcd,0xfd,0x03,0x76}) do s:write_u8(0x9f80+i-1,value) end
    cpu.state.HALT.value=0;cpu.state.IFF1.value=0;cpu.state.IFF2.value=0
    cpu.state.SP.value=0x9ff0;cpu.state.PC.value=0x9f80
    cpu.debug:bpclear()
    cpu.debug:bpset(0x043e,'1','save '..string.format('%q',current)..',8000,1000;bpdisable;g')
    m.debugger.execution_state='run';issued=frame
end
m.debugger.execution_state='run'
emu.register_frame_done(function()
    frame=frame+1;s:write_u8(0xa080,0)
    if frame==10 then issue();return end
    if index==0 then return end
    local bytes=read(current)
    if bytes then assert(#bytes==4096);result:write(bytes);issue()
    elseif frame-issued>120 then error('Original phase-clock fixture timed out') end
end)
