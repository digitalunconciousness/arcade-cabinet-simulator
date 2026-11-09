-- license:BSD-3-Clause
-- Frame-exact script runner for headless effect tests.
--
-- CABSIM_SCRIPT names a JSON plan; CABSIM_OUT a folder for the results.
-- The plan:
--   end_frame    run until this frame, then exit MAME
--   hash         false to skip hashing every frame (for speed measurements)
--   checkpoints  frames at which RAM ranges and the raw screen are saved
--   ram          [{name, space, start, end}] ranges saved at checkpoints
--   events       [{frame, type, ...}] done right after that frame is captured:
--     apply        {primitive, params}           inject a fault
--     clear_all    {}                            remove every fault
--     reset        {kind = "soft" | "hard"}      reset button or power cycle
--     button       {port, field, down}           hold or release a button
--     analog       {port, field, delta}          move an analog input
--     watch_writes {space, start, end}           record register writes
--     trace_reads  {space, start, end, until}    log which addresses are read
--
-- Frames are counted by this script across resets (a hard reset restarts
-- MAME's own frame counter), so a frame number means the same thing in a
-- faulted run and its baseline. Output:
--   hashes.txt            "<frame> <hash>" for every frame (the exported frame)
--   ram_<name>_<f>.bin    RAM ranges at checkpoints
--   frame_<f>.rgba/.json  exported screen at checkpoints
--   events.txt            applied faults, resets, errors, one per line
--   reads.txt             trace_reads output
--   done.json             written last; its absence means the run broke

local M = {}

local function hash_pixels(s)
	-- 64-bit FNV-1a over 32-bit words; Lua integers wrap like FNV needs.
	local h = -3750763034362895579
	local prime = 1099511628211
	local n = #s
	local pos = 1
	local unpack = string.unpack
	while pos + 31 <= n do
		local a, b, c, d, e, f, g, k, nxt = unpack("<I4I4I4I4I4I4I4I4", s, pos)
		h = (h ~ a) * prime; h = (h ~ b) * prime; h = (h ~ c) * prime; h = (h ~ d) * prime
		h = (h ~ e) * prime; h = (h ~ f) * prime; h = (h ~ g) * prime; h = (h ~ k) * prime
		pos = nxt
	end
	while pos <= n do
		h = (h ~ s:byte(pos)) * prime
		pos = pos + 1
	end
	return string.format("%016x", h)
end
M.hash_pixels = hash_pixels

function M.start(engine, script_path, out_dir)
	local json = require("json")
	local f = assert(io.open(script_path, "rb"))
	local plan = json.parse(f:read("a"))
	f:close()
	out_dir = out_dir or "."

	local function path(name) return out_dir .. "/" .. name end
	local function write_file(name, data)
		local fh = assert(io.open(path(name), "wb"))
		fh:write(data)
		fh:close()
	end

	local hashes = assert(io.open(path("hashes.txt"), "w"))
	local events = assert(io.open(path("events.txt"), "w"))
	local function log(...)
		events:write(table.concat({...}, " "), "\n")
		events:flush()
	end

	local checkpoints = {}
	for _, c in ipairs(plan.checkpoints or {}) do checkpoints[math.tointeger(c)] = true end
	local by_frame = {}
	for _, e in ipairs(plan.events or {}) do
		local fr = math.tointeger(e.frame)
		by_frame[fr] = by_frame[fr] or {}
		table.insert(by_frame[fr], e)
	end
	local end_frame = math.tointeger(plan.end_frame)

	local frame = -1          -- timeline frame, continuous across resets
	local last_fn = nil       -- MAME's frame number on the current machine
	local machine_started = false
	local hard_pending = false -- a power cycle was requested and hasn't happened yet
	local finished = false
	local applied = {}        -- label -> fault id
	local traces = {}

	local function screen()
		for _, s in pairs(manager.machine.screens) do return s end
	end

	local function do_event(e)
		local t = e.type
		if t == "apply" then
			local id, tier = engine:apply(e.primitive, e.params or {})
			applied[e.label or e.primitive] = id
			log("apply", frame, e.primitive, "id=" .. id, "tier=" .. tier)
		elseif t == "clear_all" then
			log("clear_all", frame, engine:clear_all())
		elseif t == "reset" then
			if e.kind == "hard" then
				hard_pending = true
				manager.machine:hard_reset()
			else
				manager.machine:soft_reset()
			end
			log("reset_requested", frame, e.kind or "soft")
		elseif t == "button" then
			engine:button(e.port, e.field, e.down)
		elseif t == "analog" then
			engine:analog_delta(e.port, e.field, math.tointeger(e.delta) or e.delta)
		elseif t == "watch_writes" then
			engine:watch_writes(e.space or ":maincpu", math.tointeger(e.start), math.tointeger(e["end"]))
		elseif t == "trace_reads" then
			local sp = manager.machine.devices[e.space or ":maincpu"].spaces["program"]
			local seen = {}
			local tap = sp:install_read_tap(math.tointeger(e.start), math.tointeger(e["end"]), "cabsim_trace",
				function(offset, data, m) seen[offset] = (seen[offset] or 0) + 1 end)
			traces[#traces + 1] = {tap = tap, seen = seen, stop = math.tointeger(e["until"])}
		else
			error("unknown event type " .. tostring(t), 0)
		end
	end

	local function finish()
		finished = true
		hashes:close()
		local lines = {}
		for _, tr in ipairs(traces) do
			for addr, n in pairs(tr.seen) do lines[#lines + 1] = string.format("0x%04x %d", addr, n) end
		end
		if #lines > 0 then
			table.sort(lines)
			write_file("reads.txt", table.concat(lines, "\n") .. "\n")
		end
		write_file("done.json", json.stringify({frame = frame, faults = engine:list()}))
		events:close()
		manager.machine:exit()
	end

	local on_reset

	local function on_frame()
		if finished or hard_pending then return end
		if not machine_started then on_reset() end
		local scr = screen()
		if not scr then return end
		local fn = scr:frame_number()
		if fn == last_fn then return end -- the notifier also fires while paused
		last_fn = fn
		frame = frame + 1

		local pixels, width, height
		if plan.hash ~= false or checkpoints[frame] then
			pixels, width, height = scr:pixels()
			pixels = engine:export_frame(pixels, width, height)
		end
		if plan.hash ~= false then
			hashes:write(frame, " ", hash_pixels(pixels), "\n")
		end

		if checkpoints[frame] then
			write_file(string.format("frame_%d.rgba", frame), pixels)
			write_file(string.format("frame_%d.json", frame),
				string.format('{"width": %d, "height": %d}', width, height))
			for _, r in ipairs(plan.ram or {}) do
				local sp = manager.machine.devices[r.space or ":maincpu"].spaces["program"]
				write_file(string.format("ram_%s_%d.bin", r.name, frame),
					sp:read_range(math.tointeger(r.start), math.tointeger(r["end"]), 8))
			end
		end

		for _, tr in ipairs(traces) do
			if tr.tap and tr.stop and frame >= tr.stop then tr.tap:remove(); tr.tap = nil end
		end

		for _, e in ipairs(by_frame[frame] or {}) do
			local ok, err = pcall(do_event, e)
			if not ok then log("error", frame, e.type, tostring(err)) end
		end

		if frame >= end_frame then finish() end
	end

	on_reset = function()
		if finished then return end
		if not machine_started or hard_pending then
			-- first start, or a power cycle: devices and spaces are new
			machine_started = true
			hard_pending = false
			last_fn = nil
			local ok, err = pcall(engine.on_machine_start, engine)
			if not ok then log("error", frame, "machine_start", tostring(err)) end
			log("machine_start", frame)
		else
			log("reset", frame)
		end
	end

	-- Subscriptions are kept in the module table: MAME drops a notifier when
	-- its subscription object is garbage-collected.
	M.subs = {
		emu.add_machine_frame_notifier(on_frame),
		emu.add_machine_reset_notifier(on_reset),
	}
end

return M
