-- Optional integration verification: original MAME renderer, synthetic RAM scenes.
-- Run only with contributor ROMs; see docs/graphics-extraction.md.
local destination = assert(os.getenv('NRALLYX_REFERENCE_DIR'), 'Set NRALLYX_REFERENCE_DIR to an ignored references directory')
assert(not destination:find('..', 1, true) and destination:find('/references/', 1, true), 'Use an absolute ignored references path without ..')
local machine = manager.machine
local space = machine.devices[':maincpu'].spaces['program']
local region = machine.memory.regions[':maincpu']
-- Stop original CPU execution in an in-memory JP 0 loop; never alter ROM files.
region:write_u8(0, 0xc3)
region:write_u8(1, 0)
region:write_u8(2, 0)
space:write_u8(0xa181, 0) -- interrupts off
local frame = 0
local codes = {0,1,31,63}
local palette=machine.palettes[':palette']
local evidence=assert(io.open(destination..'/palette-reference.txt','w'))
for i=0,31 do evidence:write(string.format('%06x\n',palette:indirect_color(i) & 0xffffff)) end
for i=0,255 do evidence:write(tostring(palette:pen_indirect(i))..'\n') end
evidence:close()
local function setup(code)
  for i=0,4095 do space:write_u8(0x8000+i, 0) end
  for i=0,15 do space:write_u8(0xa000+i, 0) end
  space:write_u8(0xa130,0)
  space:write_u8(0xa140,0)
  space:write_u8(0xa183,0)
  for row=0,15 do
    for col=0,15 do
      local offset=(row+6)*32+col+4
      space:write_u8(0x8400+offset,row*16+col)
      space:write_u8(0x8c00+offset,0x40+code)
    end
  end
end
emu.register_frame_done(function()
  frame=frame+1
  space:write_u8(0xa080,0) -- watchdog
  for i,code in ipairs(codes) do
    if frame==i*4 then setup(code) end
    if frame==i*4+2 then
      local err=machine.screens[':screen']:snapshot(destination..'/tiles-'..code..'.png')
      print('REFERENCE tiles color '..code..' '..tostring(err))
    end
  end
  for i,code in ipairs(codes) do
    if frame==24+i*4 then
      setup(0)
      for j,id in ipairs({0,1,31,63}) do
        local offset=0x14+(j-1)*2
        space:write_u8(0x8000+offset,id*4)
        space:write_u8(0x8001+offset,32+(j-1)*32)
        space:write_u8(0x8800+offset,177) -- sy 64, snapshot y 48
        space:write_u8(0x8801+offset,code)
      end
    end
    if frame==26+i*4 then
      print('REFERENCE sprites color '..code..' '..tostring(machine.screens[':screen']:snapshot(destination..'/sprites-'..code..'.png')))
    end
  end
  if frame==48 then
    setup(0)
    for id=0,7 do
      local offset=0x14+id
      space:write_u8(0x8020+offset,32+id*16)
      space:write_u8(0x8820+offset,157) -- y 96, snapshot y 80
      space:write_u8(0xa000+(offset & 15),((id ~ 7)<<1)|1)
    end
  end
  if frame==50 then
    print('REFERENCE dots '..tostring(machine.screens[':screen']:snapshot(destination..'/dots.png')))
  end
  if frame==52 then palette:set_shadow_factor(1.0) end
  if frame==54 then
    print('REFERENCE dots unshadowed '..tostring(machine.screens[':screen']:snapshot(destination..'/dots-unshadowed.png')))
  end
  if frame==56 then machine:exit() end
end)
