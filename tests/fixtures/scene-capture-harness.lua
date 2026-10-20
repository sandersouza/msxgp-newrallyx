-- Run the actual recorder against synthetic machine lifecycle events; no ROMs.
local script, destination, scenario = arg[1],arg[2],arg[3]
local frame_callback,reset_callback,map_callback
local callbacks={}
local function notify() if map_callback then map_callback('w') end end
local space={}
function space:install_write_tap(first,last,name,callback)
    callbacks[first]=callback; notify()
    return {remove=function() callbacks[first]=nil; notify() end}
end
function space:add_change_notifier(callback) map_callback=callback; return {} end
local function share(size) return {size=size,read_u8=function() return 0 end} end
local screen={frame_number=function() return 12 end,
    snapshot=function(_,path) local f=assert(io.open(path,'w'));f:write('synthetic');f:close() end}
local machine={devices={[':maincpu']={spaces={program=space}}},screens={[':screen']=screen},
    memory={shares={[':videoram']=share(4096),[':radarattr']=share(16)}},
    ioport={ports={}},time='0.2',exit=function() end}
function machine:soft_reset() reset_callback() end
manager={machine=machine}
emu={add_machine_reset_notifier=function(callback) reset_callback=callback; return {} end,
    app_version=function() return '0.289' end,
    register_frame_done=function(callback) frame_callback=callback end}
local getenv=os.getenv
os.getenv=function(name)
    if name=='NRALLYX_CAPTURE_CONFIG' then return destination..'/run.lua' end
    return getenv(name)
end
dofile(script)
if scenario=='initial-change' then notify() end -- own installation may notify asynchronously
callbacks[0xa130](0xa130,10,255); callbacks[0xa140](0xa140,20,255); callbacks[0xa183](0xa183,0,255)
frame_callback()
if scenario=='loss' then
    callbacks={}; notify() -- external write-map replacement removes the observations
elseif scenario=='reset' then
    reset_callback() -- no new register writes: old initialized values must not survive
elseif scenario=='uninitialized' then
    reset_callback(); callbacks[0xa130](0xa130,10,255)
elseif scenario=='read-change' then
    if map_callback then map_callback('r') end
end
frame_callback()
if scenario=='reset' or scenario=='uninitialized' then frame_callback() end
