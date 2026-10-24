-- Independent oracle: original contact/rock branch, with test-only returns at
-- the next subsystem boundaries. Source ROM files are never modified.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local root=assert(os.getenv('ROCK_COLLISION_OUTPUT'))
local function load(name)
 local f=assert(io.open(root..'/'..name,'rb'));local data=f:read('a');f:close();return data
end
local cases=load('cases.bin')
local rocks=load('rock-cells.bin')
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,active=0,0,false
local function byte(a,v) s:write_u8(a,v) end
local function word(a,v) byte(a,v%256);byte(a+1,math.floor(v/256)) end
local function issue()
 index=index+1
 if index>#cases/4 then out:close();m:exit();return end
 local lo,hi,x,y=cases:byte((index-1)*4+1,(index-1)*4+4)
 word(0x8079,lo+hi*256);byte(0x806d,x);byte(0x806f,y)
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f80
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then
  for a=0x8000,0x8fff do byte(a,0) end
  for a=0x97e0,0x9f1f do byte(a,0) end
  word(0x8992,0x83c0) -- empty flag list; flags/death/AI are separate stages
  for n=1,#rocks,2 do word(0x83b0+n-1,rocks:byte(n)+256*rocks:byte(n+1)) end
  for n=1,#rocks,2 do byte(rocks:byte(n)+256*rocks:byte(n+1),3) end
  -- Redirect continuations only, leaving the tested geometry, grace check,
  -- tile read and CP3 branch unchanged in the emulator's original program.
  for _,a in ipairs({0x17c5,0x1861,0x19a1}) do
   s:write_direct_u8(a,0xaf);s:write_direct_u8(a+1,0xc9)
  end
  for i,b in ipairs({0x3e,1,0xc9}) do s:write_direct_u8(0x1baa+i-1,b) end
  for i,b in ipairs({0xf3,0xcd,0x74,0x17,0x76,0x18,0xfd}) do byte(0x9f80+i-1,b) end
  active=true;issue();return
 end
 if not active then return end
 assert(cpu.state['HALT'].value~=0,'Original collision did not return')
 assert(cpu.state['SP'].value==0x83f0,'Original collision unbalanced the stack')
 local a=math.floor(cpu.state['AF'].value/256)
 local cell=cpu.state['DE'].value
 assert(a==0 or a==1,'Invalid original contact result')
 out:write(string.char(a,cell%256,math.floor(cell/256)))
 issue()
end)
