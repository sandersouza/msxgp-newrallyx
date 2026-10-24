-- Compare repeated original AI transforms, without patching the arcade ROM.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local config=dofile(assert(os.getenv('FULL_AI_CONFIG')))
local function read(path)
    local f=io.open(path,'rb');if not f then return nil end
    local bytes=f:read('a');f:close();return bytes
end
local seed=assert(read(config.output..'/source-seed.bin'))
local result=assert(io.open(config.output..'/original.bin','wb'))
local current=config.output..'/current.bin'
local index,step,frame,issued=0,0,0,0
local function restore(bytes)
    for i=1,#bytes do s:write_u8(0x8000+i-1,bytes:byte(i)) end
end
local function execute()
    os.remove(current)
    cpu.state.HALT.value=0;cpu.state.IFF1.value=0;cpu.state.IFF2.value=0
    s:write_u8(0x9ff0,0x2c);s:write_u8(0x9ff1,0x0c)
    cpu.state.SP.value=0x9ff0;cpu.state.PC.value=config.entry or 0x0cd6
    cpu.debug:bpclear()
    cpu.debug:bpset(0x0c2c,'1','save '..string.format('%q',current)..',8000,1000;bpdisable;g')
    m.debugger.execution_state='run';issued=frame
end
local function issue()
    index=index+1;step=1
    if index>#config.cases then
        result:close();local f=assert(io.open(config.output..'/complete','w'))
        f:write('ok\n');f:close();m:exit();return
    end
    restore(seed)
    local c=config.cases[index]
    for i,at in ipairs({0x8070,0x8072,0x806b,0x806a,0x805b}) do s:write_u8(at,c[i]) end
    for _,at in ipairs({0x8025,0x8026,0x8029,0x802a}) do s:write_u8(at,0) end
    s:write_u8(0x824e,7);s:write_u8(0x828f,0x30+c[8])
    for i=0,6 do
        local p=0x8088+i*32
        for _,offset in ipairs({0,1,2,19,21}) do s:write_u8(p+offset,0) end
        s:write_u8(p+3,((c[6] >> i)&1)==1 and 255 or 0)
        if config.motion==1 then
            for offset,multiplier in pairs({[4]=7,[5]=17,[6]=11,[7]=23}) do
                s:write_u8(p+offset,((index-1)+i*multiplier)&255)
            end
            if ((index-1)+i)%3==1 then
                s:write_u8(p+1,(index-1)&255);s:write_u8(p+2,c[4])
            end
        end
    end
    local guard=c[7]
    if guard==10 then for at=0x8400,0x87ff do s:write_u8(at,0) end end
    if guard==2 then s:write_u8(0x8025,0x20);s:write_u8(0x8026,2) end
    if guard==3 then s:write_u8(0x8088,1) end
    if guard==4 then s:write_u8(0x80c8+19,2) end
    if guard==5 then s:write_u8(0x80e8+21,1) end
    if guard==6 then s:write_u8(0x80a8+1,1) end
    if guard==7 then s:write_u8(0x8108+3,7) end
    if guard==8 then s:write_u8(0x8088+5,1) end
    if guard==9 then s:write_u8(0x8088+7,255) end
    execute()
end
m.debugger.execution_state='run'
emu.register_frame_done(function()
    frame=frame+1;s:write_u8(0xa080,0)
    if frame==10 then issue();return end
    if index==0 then return end
    local bytes=read(current)
    if bytes then
        assert(#bytes==4096)
        if step==3 then result:write(bytes);issue()
        else
            restore(bytes);step=step+1
            if step==3 then
                if config.cases[index][9]==1 then s:write_u8(0x8070,s:read_u8(0x8070)+1) end
                if config.cases[index][9]==2 then s:write_u8(0x805b,(s:read_u8(0x805b)+1)&255) end
            end
            execute()
        end
    elseif frame-issued>120 then error('Original repeated-AI fixture timed out') end
end)
