-- Original flag geometry/scan and collection mutation, isolated before graphics,
-- score, fuel reward and the enemy continuation. Only emulator memory is edited.
local m=manager.machine
local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('FLAGS_OUTPUT'))
local function load(name) local f=assert(io.open(root..'/'..name,'rb'));local v=f:read('a');f:close();return v end
local cases=load('cases.bin');local records=load('flag-records.bin')
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,active=0,0,false
local function byte(a,v) s:write_u8(a,v) end
local function word(a,v) byte(a,v%256);byte(a+1,math.floor(v/256)) end
local function install(a,code,direct)
 for i,b in ipairs(code) do if direct then s:write_direct_u8(a+i-1,b) else byte(a+i-1,b) end end
end
local function reset()
 for n=0,9 do
  local lo,hi,kind=records:byte(n*6+1,n*6+3)
  word(0x83c0+n*2,lo+256*hi);byte(lo+256*hi,kind)
 end
 byte(0x8023,0)
end
local function issue()
 index=index+1
 if index>#cases/5 then out:close();m:exit();return end
 local lo,hi,x,y,r=cases:byte((index-1)*5+1,(index-1)*5+5)
 if r==1 then reset() end
 word(0x8079,lo+256*hi);byte(0x806d,x);byte(0x806f,y);byte(0x9f70,0)
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83b0;cpu.state['PC'].value=0x9f80
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then
  for a=0x8000,0x8fff do byte(a,0) end
  for a=0x97e0,0x9f1f do byte(a,0) end
  word(0x8992,0x83c0)
  -- Capture original B's matched slot, replay replaced PUSH HL / LD A,1,
  -- then continue the unchanged source cell/list/type mutations.
  install(0x19a1,{0xc3,0x40,0x9f},true)
  install(0x9f40,{0x3e,11,0x90,0x32,0x70,0x9f,0xe5,0x3e,1,0xc3,0xa4,0x19})
  for _,a in ipairs({0x143d,0x146f,0x1e62,0x19d9,0x17c5,0x1861,0x1baa}) do install(a,{0xc9},true) end
  install(0x9f80,{0xf3,0xcd,0x74,0x17,0x76,0x18,0xfd})
  active=true;issue();return
 end
 if not active then return end
 assert(cpu.state['HALT'].value~=0,'Original flag consumer did not return')
 assert(cpu.state['SP'].value==0x83b0,'Original flag consumer unbalanced stack')
 local result={string.char(s:read_u8(0x9f70)),string.char(0)}
 for n=0,9 do
  local lo=s:read_u8(0x83c0+n*2);local hi=s:read_u8(0x83c1+n*2)
  result[#result+1]=string.char((lo+hi*256)==0 and 0 or 1)
 end
 for n=0,9 do
  local lo,hi=records:byte(n*6+1,n*6+2)
  result[#result+1]=string.char(s:read_u8(lo+hi*256))
 end
 out:write(table.concat(result));issue()
end)
