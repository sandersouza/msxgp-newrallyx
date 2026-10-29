-- Natural original gameplay: real coin/start/direction/smoke inputs only.
-- Never modifies original guest RAM/ROM or suppresses any sound voice.
local m=manager.machine
local s=m.devices[':maincpu'].spaces['program']
local out=assert(os.getenv('NRX_MOTION_AUDIO_OUTPUT'))
local fields={}
for _,f in pairs(m.ioport.ports[':P1'].fields) do fields[f.mask]=f end
local rows=assert(io.open(out..'/frames.tsv','w'))
local inputs=assert(io.open(out..'/inputs.tsv','w'))
local writes=assert(io.open(out..'/writes.tsv','w'))
local shadow={};for i=0,31 do shadow[i]=0 end
local frame=0
local tap=s:install_write_tap(0xa100,0xa11f,'motion_audio',function(a,v)
 if not m:side_effects_disabled() then
  shadow[a-0xa100]=v&15
  writes:write(string.format('%d %s %d %d\n',frame,tostring(m.time),a,v&15))
 end
end)
local function input(mask,down)
 assert(fields[mask]);fields[mask]:set_value(down)
 inputs:write(string.format('%d %d %d\n',frame,mask,down))
end
emu.register_frame_done(function()
 assert(tap)
 frame=frame+1
 local r={frame,tostring(m.time)}
 for _,a in ipairs({0x8020,0x81b0,0x800f,0x89f4,0x89f5,0x89f6,0x8048,0x8068,0x8069,0x806a,0x806b,0x8070,0x8072,0x8271}) do r[#r+1]=s:read_u8(a) end
 for i=0,31 do r[#r+1]=shadow[i] end
 rows:write(table.concat(r,' ')..'\n')
 if frame==1800 then input(0x80,1) end
 if frame==1804 then input(0x80,0) end
 if frame==1860 then input(0x40,1) end
 if frame==1864 then input(0x40,0) end
 if frame>=2200 then
  local t=(frame-2200)%480
  if t%120==0 then
   for _,mask in ipairs({4,8,16,32}) do input(mask,0) end
   input(({32,4,16,8})[t//120+1],1)
  end
  if t%120==40 then input(2,1) end
  if t%120==48 then input(2,0) end
 end
 if frame==4000 then
  rows:close();inputs:close();writes:close()
  local f=assert(io.open(out..'/complete','w'));f:write('ok\n');f:close();m:exit()
 end
end)
