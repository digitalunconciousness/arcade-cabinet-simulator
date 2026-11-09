-- license:BSD-3-Clause
-- Stage 0 audit probe, loaded with -autoboot_script.
--
-- Records what the running game shows and holds, so a faulted run can be
-- compared with a baseline frame by frame:
--   hashes.txt    one line per emulated frame: "<frame> <hash of screen pixels>"
--   ram_<f>.bin   main CPU RAM 0x0000-0x07FF at each checkpoint frame
--   frame_<f>.rgba + frame_<f>.json   raw screen pixels at each checkpoint
--   events.txt    machine resets (a watchdog reset shows up here)
--   paused.json   written when the probe pauses for fault injection
--   done.json     written just before the probe makes MAME exit
--
-- Settings come from the environment: AUDIT_OUT (output folder),
-- AUDIT_PAUSE_FRAME, AUDIT_END_FRAME, AUDIT_CHECKPOINTS ("700,900,...").

local out_dir = assert(os.getenv("AUDIT_OUT"), "AUDIT_OUT is not set")
local pause_at = tonumber(os.getenv("AUDIT_PAUSE_FRAME") or "600")
local end_at = tonumber(os.getenv("AUDIT_END_FRAME") or "1200")
local checkpoints = {}
for n in (os.getenv("AUDIT_CHECKPOINTS") or ""):gmatch("%d+") do
	checkpoints[tonumber(n)] = true
end

local function path(name) return out_dir .. "/" .. name end

local function write_file(name, data)
	local f = assert(io.open(path(name), "wb"))
	f:write(data)
	f:close()
end

-- 64-bit FNV-1a over 32-bit words. Lua integers wrap on overflow, which is
-- the modular arithmetic FNV needs. Good enough to tell frames apart.
local FNV_OFFSET = -3750763034362895579 -- 0xcbf29ce484222325
local FNV_PRIME = 1099511628211
local function hash_pixels(s)
	local h = FNV_OFFSET
	local n = #s
	local pos = 1
	local unpack = string.unpack
	while pos + 31 <= n do
		local a, b, c, d, e, f, g, k, nxt = unpack("<I4I4I4I4I4I4I4I4", s, pos)
		h = (h ~ a) * FNV_PRIME; h = (h ~ b) * FNV_PRIME
		h = (h ~ c) * FNV_PRIME; h = (h ~ d) * FNV_PRIME
		h = (h ~ e) * FNV_PRIME; h = (h ~ f) * FNV_PRIME
		h = (h ~ g) * FNV_PRIME; h = (h ~ k) * FNV_PRIME
		pos = nxt
	end
	while pos <= n do
		h = (h ~ s:byte(pos)) * FNV_PRIME
		pos = pos + 1
	end
	return string.format("%016x", h)
end

local hashes = assert(io.open(path("hashes.txt"), "w"))
local events = assert(io.open(path("events.txt"), "w"))
local last_frame = -1
local paused_once = false
local finished = false

local function screen()
	for _, s in pairs(manager.machine.screens) do return s end
end

local function cpu_space()
	return manager.machine.devices[":maincpu"].spaces["program"]
end

local function on_frame()
	if finished then return end
	local scr = screen()
	if not scr then return end
	local frame = scr:frame_number()
	if frame == last_frame then return end -- the notifier also fires while paused
	last_frame = frame

	local pixels, width, height = scr:pixels()
	hashes:write(frame, " ", hash_pixels(pixels), "\n")

	if checkpoints[frame] then
		write_file(string.format("frame_%d.rgba", frame), pixels)
		write_file(string.format("frame_%d.json", frame),
			string.format('{"width": %d, "height": %d}', width, height))
		write_file(string.format("ram_%d.bin", frame), cpu_space():read_range(0x0000, 0x07ff, 8))
	end

	if frame >= pause_at and not paused_once then
		paused_once = true
		hashes:flush()
		emu.pause()
		write_file("paused.json", string.format('{"frame": %d}', frame))
	end

	if frame >= end_at then
		finished = true
		hashes:close()
		events:close()
		write_file("done.json", string.format('{"frame": %d}', frame))
		manager.machine:exit()
	end
end

-- Subscriptions are kept in globals: MAME drops a notifier when its
-- subscription object is garbage-collected.
audit_frame_sub = emu.add_machine_frame_notifier(on_frame)
audit_reset_sub = emu.add_machine_reset_notifier(function ()
	if finished then return end
	events:write("reset ", tostring(last_frame), "\n")
	events:flush()
end)
