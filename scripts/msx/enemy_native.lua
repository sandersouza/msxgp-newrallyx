-- Independent original selected enemy component; no full foreground/IRQ.
local m=manager.machine;local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local root=assert(os.getenv('ENEMY_OUTPUT'))
local count=tonumber(os.getenv('ENEMY_COUNT') or '1')
assert(count==1 or count==2,'Unsupported diagnostic population')
local function load(n) local f=assert(io.open(root..'/'..n,'rb'));local d=f:read('a');f:close();return d end
local cases=load('cases.bin');local seed=load('source-seed.bin')
local out=assert(io.open(root..'/original.bin','wb'))
local frame,index,active=0,0,false
local function byte(a,v) s:write_u8(a,v) end
local function word(a,v) byte(a,v%256);byte(a+1,math.floor(v/256)) end
local function issue()
 index=index+1;if index>#cases/5 then out:close();m:exit();return end
 local p=(index-1)*5;local kind,a,b,c,d=cases:byte(p+1,p+5)
 local code={0xf3}
 local function add(v) code[#code+1]=v end
 local function bytes(t) for _,v in ipairs(t) do add(v) end end
 local function call(a) bytes({0xcd,a%256,math.floor(a/256)}) end
 if kind~=0 then for i=1,4096 do byte(0x8000+i-1,seed:byte(i)) end end
 byte(0x9f41,0)
 if kind==2 then
  byte(0x824e,count);word(0x8052,0x2d0a);word(0x8054,0)
  call(0x0c6c)
  bytes({0x21,0x0a,0x2d,0x22,0x52,0x80})
  call(0x0ab5);call(0x15bd)
  bytes({0x2a,0x27,0x80,0x22,0x69,0x80,0x22,0x2d,0x80})
 elseif kind==1 then
  word(0x8004,0x8093);byte(0x8074,112);byte(0x8076,116)
  byte(0x8094,a);byte(0x8096,b);byte(0x8093,c)
  bytes({0xdd,0x21,0x68,0x80,0xfd,0x21,0x04,0x80,0x06,5});call(0x038a)
 else
  byte(0x9f40,a)
  bytes({0xdd,0x21,0x14,0x88,0x21,0x15,0x80,0xfd,0x21,0x02,0x80,0x06,6});call(0x022b)
  call(0x0069);call(0x1052)
  if b~=0 then call(0x1ddf) end
  bytes({0xdd,0x21,0x68,0x80,0xfd,0x21,0x04,0x80,0x06,5});call(0x038a)
  bytes({0x3a,0x41,0x9f,0xb7,0xcc,0xd6,0x0c})
  for _,a in ipairs({0x8050,0x8051}) do bytes({0x3a,a%256,math.floor(a/256),0xc6,7,0xfe,15,0xd4,a==0x8050 and 0xbf or 7,a==0x8050 and 0x11 or 0x12}) end
  call(0x15bd)
 end
 add(0x76);bytes({0x18,0xfd})
 for i,v in ipairs(code) do byte(0x9f80+i-1,v) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83d0;cpu.state['PC'].value=0x9f80
end
emu.register_frame_done(function()
 frame=frame+1;byte(0xa080,0)
 if frame==10 then
  for _,a in ipairs({0x02eb,0x03c3,0x0bd1,0x0c2c,0x124f,0x1273,0x127e,0x12a8}) do s:write_direct_u8(a,0xc9) end
  for _,a in ipairs({0x03b9,0x1074,0x10de,0x11bf,0x1207,0x15c5,0x1618}) do s:write_direct_u8(a,0) end
  for i,v in ipairs({0x3e,1,0x32,0x41,0x9f,0xc9}) do s:write_direct_u8(0x18c0+i,v) end
  active=true;issue();return
 end
 if not active then return end
 assert(cpu.state['HALT'].value~=0,'Original enemy component did not return')
 assert(cpu.state['SP'].value==0x83d0,'Original enemy stack imbalance')
 local result={}
 for _,range in ipairs({{0x8000,0x1a8},{0x81b5,1},{0x8248,10},{0x8814,12}}) do
  for a=range[1],range[1]+range[2]-1 do
   local v=s:read_u8(a)
   if a>=0x8002 and a<0x800e and a%2==1 then
    local ptr=s:read_u16(a-1)
    assert(ptr==0 or ptr>=0x8073 and ptr<=0x8173 and (ptr-0x8073)%32==0,'Unexpected original virtual sprite pointer')
    if ptr~=0 then v=v+0x60 end
   end
   result[#result+1]=string.char(v)
  end
 end
 result[#result+1]=string.char(s:read_u8(0x9f41));out:write(table.concat(result));issue()
end)
