-- Contributor ROM acquisition: real coin/start first, isolated native redraw check second.
local m = manager.machine
local cpu = m.devices[':maincpu']
local s = cpu.spaces['program']
local root = assert(os.getenv('STAGE_ONE_OUTPUT'))
local fields = {}
for _,p in pairs(m.ioport.ports) do for _,f in pairs(p.fields) do fields[f.name]=f end end
local frame, pending, wait = 0, 1, 0
local windows = {}
for _,y in ipairs({-1,9,19,29,39,49,59}) do
 for _,x in ipairs({-1,9,19,29}) do windows[#windows+1]={x,y} end
end
local function save(name,first,n)
 local bytes={}
 for a=first,first+n-1 do bytes[#bytes+1]=string.char(s:read_u8(a)) end
 local f=assert(io.open(root..'/'..name,'wb'));f:write(table.concat(bytes));f:close()
end
local function redraw(w)
 s:write_u8(0xa080,0) -- watchdog
 s:write_u8(0x8052,w[1]%256);s:write_u8(0x8053,w[2]%256)
 for _,a in ipairs({0x8054,0x8055,0x804f,0x8050,0x8051}) do s:write_u8(a,0) end
 s:write_u8(0x804d,16) -- native destination starts at tile (0,0)
 -- DI; CALL native full-window redraw; HALT; JR back to HALT.
 local harness={0xf3,0xcd,0xe3,0x12,0x76,0x18,0xfd}
 for i,b in ipairs(harness) do s:write_u8(0x9f00+i-1,b) end
 cpu.state['HALT'].value=0
 cpu.state['SP'].value=0x9ff0;cpu.state['PC'].value=0x9f00
 wait=32
end
emu.register_frame_done(function()
 frame=frame+1
 if frame==1800 then fields['Coin 1']:set_value(1) end
 if frame==1804 then fields['Coin 1']:set_value(0) end
 if frame==1860 then fields['1 Player Start']:set_value(1) end
 if frame==1864 then fields['1 Player Start']:set_value(0) end
 if frame==2200 then save('video.bin',0x8000,4096);save('work.bin',0x9800,2048) end
 if frame==2200 then redraw(windows[pending]) end
 if frame>2200 then
  s:write_u8(0xa080,0)
  wait=wait-1
  if wait==0 then
   local w=windows[pending]
   if cpu.state['PC'].value~=0x9f05 and cpu.state['PC'].value~=0x9f04 then
    save('failed-video.bin',0x8000,4096);save('failed-harness.bin',0x9f00,256)
    error('Native redraw did not halt: '..cpu.state['PC'].value) end
   save('window-'..w[1]..'-'..w[2]..'.bin',0x8000,4096)
   pending=pending+1
   if pending>#windows then
    local f=assert(io.open(root..'/complete','w'));f:write('ok\n');f:close();m:exit()
   else redraw(windows[pending]) end
  end
 end
end)
