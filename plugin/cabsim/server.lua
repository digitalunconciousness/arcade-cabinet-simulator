-- license:BSD-3-Clause
-- Sim Control Protocol v1 (docs/protocol/scp-v1.md) over a local TCP socket.
--
-- Newline-terminated JSON objects both ways; one reply per request. Every
-- reply has "ok"; a request's "req" field, if present, is echoed back.
-- Stage 1 serves one client per MAME session.

local M = {}

local PROTOCOL = "scp/1"

function M.start(engine, port)
	local json = require("json")
	local addr = "socket.127.0.0.1:" .. tostring(port)
	local sock = emu.file("", 7) -- 7 = read | write | create, a socket for "socket." paths
	local err = sock:open(addr)
	if err then
		emu.print_error("cabsim: can't listen on " .. addr .. ": " .. tostring(err))
		return
	end
	emu.print_info("cabsim: listening on " .. addr)
	local buffer = ""

	local function state()
		local m = manager.machine
		local scr
		for _, s in pairs(m.screens) do scr = s break end
		return {
			ok = true,
			romset = emu.romname(),
			paused = m.paused,
			frame = scr and scr:frame_number() or nil,
			faults = engine:list(),
		}
	end

	local handlers = {}
	handlers["hello"] = function(r)
		return {ok = true, protocol = PROTOCOL, app = emu.app_name(), version = emu.app_version(), romset = emu.romname()}
	end
	handlers["state"] = function(r) return state() end
	handlers["pause"] = function(r) emu.pause() return state() end
	handlers["resume"] = function(r) emu.unpause() return state() end
	handlers["reset"] = function(r)
		if r.kind == "hard" then manager.machine:hard_reset() else manager.machine:soft_reset() end
		return {ok = true, reset = r.kind or "soft"}
	end
	handlers["fault.apply"] = function(r)
		local id, tier = engine:apply(r.primitive, r.params or {})
		return {ok = true, id = id, tier = tier}
	end
	handlers["fault.clear"] = function(r)
		return {ok = engine:clear(math.tointeger(r.id)), id = r.id}
	end
	handlers["fault.clear_all"] = function(r) return {ok = true, cleared = engine:clear_all()} end
	handlers["fault.list"] = function(r) return {ok = true, faults = engine:list()} end
	handlers["input.button"] = function(r)
		return {ok = true, down = engine:button(r.port, r.field, r.down and true or false)}
	end
	handlers["input.analog_delta"] = function(r)
		return {ok = true, position = engine:analog_delta(r.port, r.field, math.tointeger(r.delta) or 0)}
	end

	local function reply(obj, req)
		if req ~= nil then obj.req = req end
		sock:write(json.stringify(obj) .. "\n")
	end

	local function handle(line)
		local ok, r = pcall(json.parse, line)
		if not ok or type(r) ~= "table" then
			reply({ok = false, error = "invalid JSON"})
			return
		end
		local h = handlers[r.cmd]
		if not h then
			reply({ok = false, error = "unknown command: " .. tostring(r.cmd)}, r.req)
			return
		end
		local ok2, result = pcall(h, r)
		if not ok2 then
			reply({ok = false, error = tostring(result)}, r.req)
		else
			reply(result, r.req)
		end
	end

	-- Pumped from the periodic callback, which also runs while paused.
	M.periodic = emu.register_periodic(function()
		repeat
			local chunk = sock:read(4096)
			if chunk and #chunk > 0 then buffer = buffer .. chunk end
		until not chunk or #chunk < 4096
		while true do
			local nl = buffer:find("\n", 1, true)
			if not nl then break end
			local line = buffer:sub(1, nl - 1)
			buffer = buffer:sub(nl + 1)
			if #line > 0 then handle(line) end
		end
	end)
end

return M
