-- license:BSD-3-Clause
-- cabsim: the fault engine for arcade-cabinet-simulator, inside MAME.
--
-- Load with:  mame <set> -pluginspath "<mame>/plugins;<repo>/plugin" -plugin cabsim
-- Environment:
--   CABSIM_PORT    serve Sim Control Protocol v1 on 127.0.0.1:<port>
--   CABSIM_SCRIPT  run a frame-exact effect-test plan (timeline.lua) and exit
--   CABSIM_OUT     folder for the plan's results (default: current folder)

local exports = {
	name = "cabsim",
	version = "0.1.0",
	description = "Fault engine for arcade-cabinet-simulator",
	license = "BSD-3-Clause",
	author = {name = "arcade-cabinet-simulator"},
}

function exports.startplugin()
	local engine = require("cabsim/primitives").new()
	exports.engine = engine
	local script = os.getenv("CABSIM_SCRIPT")
	if script and #script > 0 then
		require("cabsim/timeline").start(engine, script, os.getenv("CABSIM_OUT"))
	end
	local port = tonumber(os.getenv("CABSIM_PORT") or "")
	if port then
		require("cabsim/server").start(engine, port)
	end
end

return exports
