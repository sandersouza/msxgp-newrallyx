-- Isolated original rock placement and redraw, after a real first-stage start.
-- This is a presentation fixture, not an untouched later-round gameplay trace.
local m = manager.machine
local cpu = m.devices[':maincpu']
local s = cpu.spaces['program']
local root = assert(os.getenv('ROCKS_OUTPUT'))
local fields = {}
for _,p in pairs(m.ioport.ports) do for _,f in pairs(p.fields) do fields[f.name]=f end end
local frame, wait, index, phase = 0, 0, 1, 'boot'
local windows = {}
for _,y in ipairs({-1,9,19,29,39,49,59}) do
 for _,x in ipairs({-1,9,19,29}) do windows[#windows+1]={x,y} end
end
local function word(a) return s:read_u8(a)+256*s:read_u8(a+1) end
local function save(name,first,n)
 local bytes={}
 for a=first,first+n-1 do bytes[#bytes+1]=string.char(s:read_u8(a)) end
 local f=assert(io.open(root..'/'..name,'wb'));f:write(table.concat(bytes));f:close()
end
local function run(bytes)
 for i,b in ipairs(bytes) do s:write_u8(0x9f00+i-1,b) end
 cpu.state['HALT'].value=0
 cpu.state['SP'].value=0x9ff0;cpu.state['PC'].value=0x9f00
 wait=32
end
local function redraw(w)
 s:write_u8(0x8052,w[1]%256);s:write_u8(0x8053,w[2]%256)
 for _,a in ipairs({0x8054,0x8055,0x804f,0x8050,0x8051}) do s:write_u8(a,0) end
 s:write_u8(0x804d,16)
 run({0xf3,0xcd,0xe3,0x12,0x76,0x18,0xfd})
end
emu.register_frame_done(function()
 frame=frame+1
 if frame==1800 then fields['Coin 1']:set_value(1) end
 if frame==1804 then fields['Coin 1']:set_value(0) end
 if frame==1860 then fields['1 Player Start']:set_value(1) end
 if frame==1864 then fields['1 Player Start']:set_value(0) end
 if frame==2200 then
  save('base-video.bin',0x8000,4096);save('base-work.bin',0x9800,2048)
  -- Original parameter record 3 selects two rocks and the same maze bitmap.
  s:write_u8(word(0x898a),3);s:write_u8(0x8292,0)
  run({0xf3,0xcd,0x1f,0x1b,0xcd,0x43,0x13,0x76,0x18,0xfd})
  phase='placement'
 elseif frame>2200 then
  s:write_u8(0xa080,0)
  wait=wait-1
  if wait==0 then
   local pc=cpu.state['PC'].value
   if phase=='placement' then
    assert(pc==0x9f07 or pc==0x9f08,'Original placement did not halt')
    assert(s:read_u8(0x8251)==2,'Unexpected original rock count')
    assert(s:read_u8(0x828f)==0x30,'Rock fixture changed the maze layout')
    save('placement-video.bin',0x8000,4096)
    -- Equivalent to the original $094b..$0950 board stamping. Keep all
    -- first-stage flags untouched so only rock presentation changes in A/B.
    local table=word(0x8996)
    for n=0,1 do
     local address=word(table+n*2)
     assert(address>=0x9800 and address<0x9f00,'Invalid original rock pointer')
     assert(s:read_u8(address)==0,'Rock fixture overlaps an existing object/wall')
     s:write_u8(address,3)
    end
    save('video.bin',0x8000,4096);save('work.bin',0x9800,2048)
    phase='redraw';redraw(windows[index])
   else
    assert(pc==0x9f04 or pc==0x9f05,'Original rock redraw did not halt')
    local w=windows[index]
    save('window-'..w[1]..'-'..w[2]..'.bin',0x8000,4096)
    index=index+1
    if index>#windows then
     local f=assert(io.open(root..'/complete','w'));f:write('ok\n');f:close();m:exit()
    else redraw(windows[index]) end
   end
  end
 end
end)
