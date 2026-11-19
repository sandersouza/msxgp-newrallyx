-- Issue42: read-only observers during a real original-ROM credit/start.
-- Only keyboard input is supplied. No RAM/register/ROM patches or guest calls.
local m=manager.machine
local cpu=m.devices[':maincpu'];local s=cpu.spaces['program']
local out=assert(os.getenv('NRX42_OUTPUT'))
local delay=tonumber(os.getenv('NRX42_START_DELAY') or '0')
local frame=0;local placement=nil;local rng_calls=0;local background_calls=0
local fields={}
for _,p in pairs(m.ioport.ports) do
 for _,f in pairs(p.fields) do fields[f.name]=f end
end
local log=assert(io.open(out..'/events.tsv','w'))
log:write('event\tframe\tmode\tround\tlayout\trng\trng_calls\tbackground_calls\tflags\n')
local function word(a) return s:read_u8(a)+256*s:read_u8(a+1) end
local function hex(a,n)
 local b={};for i=0,n-1 do b[#b+1]=string.format('%02x',s:read_u8(a+i)) end
 return table.concat(b)
end
local function emit(name,flags)
 local roundptr=word(0x898a)
 log:write(table.concat({name,frame,s:read_u8(0x8020),s:read_u8(roundptr),
  s:read_u8(0x828f),word(0x8000),rng_calls,background_calls,flags or '-'},'\t')..'\n')
 log:flush()
end
local taps={}
local function observe(pc,name,callback)
 taps[#taps+1]=s:install_read_tap(pc,pc,name,function(a,v)
  if not m:side_effects_disabled() and cpu.state.PC.value==a then callback() end
 end)
end
observe(0x0f24,'nrx42_rng',function()
 rng_calls=rng_calls+1
 if word(cpu.state.SP.value)==0x03cd then background_calls=background_calls+1 end
end)
observe(0x1379,'nrx42_flags_begin',function()
 if frame>=1860+delay then emit('flags_begin') end
end)
observe(0x140c,'nrx42_flags_end',function()
 if frame>=1860+delay then
  local ptr=word(0x8992);placement=hex(ptr,20)
  emit('flags_end',placement)
 end
end)
observe(0x0952,'nrx42_board_ready',function()
 if placement then
  emit('board_ready',placement)
  local f=assert(io.open(out..'/board.bin','wb'))
  for a=0x9800,0x9eff do f:write(string.char(s:read_u8(a))) end
  f:close();log:close()
  local done=assert(io.open(out..'/complete','w'));done:write('ok\n');done:close()
  m:exit()
 end
end)
emu.register_frame_done(function()
 assert(#taps==4);frame=frame+1
 if frame==1800 then fields['Coin 1']:set_value(1) end
 if frame==1804 then fields['Coin 1']:set_value(0) end
 if frame==1860+delay then fields['1 Player Start']:set_value(1) end
 if frame==1864+delay then fields['1 Player Start']:set_value(0) end
 if frame>2600+delay then error('Natural flag capture timeout') end
end)
