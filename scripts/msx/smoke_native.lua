-- Independent original smoke activation, bitmap tiles and enemy stun/expiry.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('SMOKE_OUTPUT'))
local function load(n) local f=assert(io.open(root..'/'..n,'rb'));local d=f:read('a');f:close();return d end
local flag_replay=os.getenv('SMOKE_FLAG_REPLAY')=='1'
local replay=os.getenv('SMOKE_REPLAY')=='1' or flag_replay
local cases=not replay and load('cases.bin') or nil
local seed=not replay and load('source-seed.bin') or nil
local seeds=replay and load('seeds.bin') or nil
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,active=0,0,false
local function byte(a,v) s:write_u8(a,v) end
local function word(a,v) byte(a,v%256);byte(a+1,math.floor(v/256)) end
local function issue()
 if replay then
  index=index+1;if index>#seeds/4096 then out:close();m:exit();return end
  local state=seeds:sub((index-1)*4096+1,index*4096)
  for i=1,4096 do byte(0x8000+i-1,state:byte(i)) end
  byte(0x9f40,state:byte(0x3f1))
  local call=flag_replay and {0xf3,0xdd,0x21,0x68,0x80,0xcd,0xd9,0x19,0x76,0x18,0xfd} or {0xf3,0xcd,0x64,0x0f,0x76,0x18,0xfd}
  for i,v in ipairs(call) do byte(0x9f80+i-1,v) end
  cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83d0;cpu.state['PC'].value=0x9f80
  return
 end
 index=index+1;if index>#cases/18 then out:close();m:exit();return end
 local c={cases:byte((index-1)*18+1,index*18)}
 local kind,hist,joy,pending,fuel,frac,round,enabled,flag,code,attr,mx,my,px,py,age,dx,dy=table.unpack(c)
 for i=1,4096 do byte(0x8000+i-1,seed:byte(i)) end
 local instructions={0xf3}
 local function add(t) for _,v in ipairs(t) do instructions[#instructions+1]=v end end
 if kind==2 then
  byte(0x824e,1)
  add({0xcd,0x6c,0x0c,0x21,0x0a,0x2d,0x22,0x52,0x80,0x21,0,0,0x22,0x54,0x80,0xcd,0xb5,0x0a,0xcd,0xbd,0x15})
 end
 for i=0,1023 do byte(0x8400+i,code);byte(0x8c00+i,attr) end
 byte(0x8290,hist);byte(0x8291,pending);byte(0x9f40,joy)
 byte(0x826b,fuel);byte(0x826a,frac);byte(0x81b0,round);byte(0x8021,enabled)
 byte(0x8077,flag);byte(0x804d,mx);byte(0x804f,my)
 byte(0x8074,px);byte(0x8076,py);byte(0x89f4,0)
 if kind==1 then
  local col=math.floor(((mx+px+3)%256)/8)
  local row=math.floor(((-my-py-8)%256)/8)
  for y=0,2 do for x=0,2 do byte(0x8400+((row+y)%32)*32+(col+x)%32,0xbd+y*3+x) end end
  byte(0x8088,age);byte(0x809d,1);byte(0x8097,flag)
  byte(0x8094,(px+dx*8)%256);byte(0x8096,(py-dy*8)%256)
  add({0xdd,0x21,0x88,0x80,0xcd,0x85,0x01})
 elseif kind==2 then add({0xcd,0xd6,0x0c})
 else add({0xcd,0x64,0x0f}) end
 add({0x76,0x18,0xfd})
 for i,v in ipairs(instructions) do byte(0x9f80+i-1,v) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83d0;cpu.state['PC'].value=0x9f80
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then
  if flag_replay then s:write_direct_u8(0x1a33,0xc9) end
  for _,a in ipairs({0x02eb,0x03c3,0x0bd1,0x0c2c,0x124f,0x1273,0x127e,0x12a8}) do s:write_direct_u8(a,0xc9) end
  for _,a in ipairs({0x03b9,0x1074,0x10de,0x15c5,0x1618}) do s:write_direct_u8(a,0) end
  active=true;issue();return
 end
 if not active then return end
 assert(cpu.state['HALT'].value~=0,'Original smoke component did not return')
 assert(cpu.state['SP'].value==0x83d0,'Original smoke stack imbalance')
 local result={}
 for _,range in ipairs({{0x826a,2},{0x8290,2},{0x89f4,1},{0x8088,32},{0x81b5,1},{0x8400,1024},{0x8c00,1024}}) do
  for a=range[1],range[1]+range[2]-1 do result[#result+1]=string.char(s:read_u8(a)) end
 end
 out:write(table.concat(result));issue()
end)
