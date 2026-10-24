-- Execute the original post-flag parameter dispatch without foreground/IRQs.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('PARAMETERS_OUTPUT'))
local function load(n) local f=assert(io.open(root..'/'..n,'rb'));local d=f:read('a');f:close();return d end
local seed=load('source-seed.bin');local cases=load('cases.bin')
local out=assert(io.open(root..'/original.bin','wb'));local frame,index,active=0,0,false
local fields={0x828f,0x82b1,0x82d6,0x824e,0x826e,0x8288,0x8251}
local function issue()
 index=index+1;if index>#cases/4 then out:close();m:exit();return end
 for i=1,4096 do s:write_u8(0x8000+i-1,seed:byte(i)) end
 local p=(index-1)*4
 for i,a in ipairs({0x81b0,0x8271,0x828a,0x8292}) do s:write_u8(a,cases:byte(p+i)) end
 for i,b in ipairs({0xf3,0xcd,0x1f,0x1b,0x76,0x18,0xfd}) do s:write_u8(0x9f80+i-1,b) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f80
end
emu.register_frame_done(function()
 frame=frame+1;s:write_u8(0xa080,0)
 if frame==10 then active=true;issue();return end
 if not active then return end
 assert(cpu.state['HALT'].value~=0 and cpu.state['SP'].value==0x83f0,'Parameters did not return')
 local result={}
 for _,a in ipairs(fields) do result[#result+1]=string.char(s:read_u8(a)) end
 for a=0x8025,0x802c do result[#result+1]=string.char(s:read_u8(a)) end
 out:write(table.concat(result));issue()
end)
