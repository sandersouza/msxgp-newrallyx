-- Execute the contributor's original player routines as a movement oracle.
-- Two in-memory harness edits replace the main-loop continuation with RET and
-- retain DI at the renderer-owned interrupt boundary. Source ROM files stay intact;
-- steering, collision, arithmetic, animation and bitmap bytes are unchanged.
local m=manager.machine
local cpu=m.devices[':maincpu']
local s=cpu.spaces['program']
local root=assert(os.getenv('PLAYER_VERIFY_OUTPUT'))
local f=assert(io.open(root..'/commands.bin','rb'));local commands=f:read('a');f:close()
local frame,index,pending=0,0,false
local active=false
local out=assert(io.open(root..'/native.bin','wb'))
local ticks=0
local function byte(a,v) s:write_u8(a,v) end
local function word(a,v) byte(a,v%256);byte(a+1,math.floor(v/256)) end
local function start(code)
 for i,b in ipairs(code) do byte(0x9f00+i-1,b) end
 cpu.state['HALT'].value=0;cpu.state['SP'].value=0x83f0;cpu.state['PC'].value=0x9f00
 pending=true
end
local function issue()
 index=index+1
 if index>#commands/3 then out:close();m:exit();return end
 local count,joy,reset=commands:byte((index-1)*3+1,(index-1)*3+3)
 local code={0xf3}
 local function call(a) code[#code+1]=0xcd;code[#code+1]=a%256;code[#code+1]=math.floor(a/256) end
 if reset==1 then
  for a=0x8000,0x8fff do byte(a,0) end
  byte(0x8020,1);word(0x8027,0x0220);byte(0x828f,0x30);word(0x899e,0x9f80)
  call(0x0c6c)
  -- Original initial forward speed; the test starts already driving upward.
  for _,v in ipairs({0x2a,0x27,0x80,0x22,0x69,0x80,0x22,0x2d,0x80}) do code[#code+1]=v end
  ticks=0
 end
 byte(0x9f80,joy)
 for n=1,count do
  call(0x0069);call(0x1052);ticks=ticks+1
  if ticks%4==0 then call(0x1ddf) end
 end
 code[#code+1]=0x76;code[#code+1]=0x18;code[#code+1]=0xfd
 start(code)
end
emu.register_frame_done(function()
 frame=frame+1
 byte(0xa080,0)
 if frame==10 then
  s:write_direct_u8(0x0c2c,0xc9)
  s:write_direct_u8(0x1074,0x00)
  s:write_direct_u8(0x10de,0x00)
  active=true;issue();return
 end
 if not active then return end
 if pending then
  if cpu.state['HALT'].value==0 then
   error(string.format('Native movement did not return to harness: frame=%d command=%d PC=%04x SP=%04x',frame,index,cpu.state['PC'].value,cpu.state['SP'].value))
  end
  local bytes={}
  for a=0x8000,0x8fff do bytes[#bytes+1]=string.char(s:read_u8(a)) end
  out:write(table.concat(bytes));pending=false;issue()
 end
end)
