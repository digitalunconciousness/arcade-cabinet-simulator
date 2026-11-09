-- license:BSD-3-Clause
-- Fault primitives for the cabsim plugin.
--
-- Each primitive acts on an emulated interface the game's own code talks to
-- (a memory range, a ROM region, a CPU input line, a device clock, an input
-- port), so the symptom comes out of the running game. Nothing here knows
-- which game is running: every parameter names an explicit device tag,
-- address range, region or port.
--
-- Usage:
--   local engine = require("cabsim/primitives").new()
--   local id = engine:apply("data_bit_stuck", {space = ":maincpu", start = 0x400, ["end"] = 0x7bf, bit = 3, level = 0})
--   engine:clear(id)
--
-- Active faults are applied again after a hard reset (a power cycle), so a
-- broken part stays broken until it is cleared.

local M = {}

local Engine = {}
Engine.__index = Engine

-- ------------------------------------------------------------------ helpers

local function num(v, what)
	local n = tonumber(v)
	if n == nil then error(what .. " must be a number, got " .. tostring(v), 0) end
	return math.tointeger(n) or n
end

local function opt_num(v, default)
	if v == nil then return default end
	return num(v, "value")
end

local function device(tag)
	local dev = manager.machine.devices[tag]
	if not dev then error("no device " .. tostring(tag), 0) end
	return dev
end

local function space(tag, name)
	local dev = device(tag)
	local sp = dev.spaces[name or "program"]
	if not sp then error("device " .. tag .. " has no " .. (name or "program") .. " space", 0) end
	if sp.data_width ~= 8 then error("only 8-bit data buses are supported, " .. tag .. " is " .. sp.data_width, 0) end
	return sp
end

local function region(tag)
	local r = manager.machine.memory.regions[tag]
	if not r then error("no memory region " .. tostring(tag), 0) end
	return r
end

local function force_bit(value, mask, level)
	if level == 1 then return value | mask end
	return value & (~mask) & 0xff
end

local function level_of(p)
	local l = num(p.level, "level")
	if l ~= 0 and l ~= 1 then error("level must be 0 or 1", 0) end
	return l
end

local function range_of(p)
	local s = num(p.start, "start")
	local e = num(p["end"], "end")
	if e < s then error("end is below start", 0) end
	return s, e
end

-- Writes made by a primitive itself pass through its own taps; this flag
-- keeps those taps from acting on them a second time.
local inside = false
local function self_write(sp, addr, value)
	inside = true
	local ok, err = pcall(sp.write_u8, sp, addr, value)
	inside = false
	if not ok then error(err, 0) end
end

-- ----------------------------------------------------------- the primitives
-- Each entry: apply(engine, params, record) sets record.undo (a function)
-- and may set record.taps, record.video (a frame transform) or
-- record.input (an input filter). tier documents the fidelity tier.

local P = {}

-- One data line of a RAM range stuck at a level. The write tap stores the
-- forced value (so the video hardware, which reads the stored bytes, shows
-- it too); the read tap forces the bit on every CPU read. The range is
-- rewritten through the bus once so handlers such as tile-dirty marking run.
P.data_bit_stuck = {
	tier = "A",
	apply = function(engine, p, rec)
		local sp = space(p.space or ":maincpu", p.space_name)
		local s, e = range_of(p)
		local mask = 1 << num(p.bit, "bit")
		local level = level_of(p)
		for a = s, e do
			self_write(sp, a, force_bit(sp:read_u8(a), mask, level))
		end
		local f = function(offset, data, m)
			if inside then return nil end
			return force_bit(data, mask, level)
		end
		rec.taps = {
			sp:install_read_tap(s, e, "cabsim_" .. rec.id .. "_r", f),
			sp:install_write_tap(s, e, "cabsim_" .. rec.id .. "_w", f),
		}
	end,
}

-- One bit of one cell stuck: data_bit_stuck over a single address.
P.ram_cell_stuck = {
	tier = "A",
	apply = function(engine, p, rec)
		local q = {space = p.space, space_name = p.space_name, start = p.addr, ["end"] = p.addr, bit = p.bit, level = p.level}
		return P.data_bit_stuck.apply(engine, q, rec)
	end,
}

-- One address line of a RAM chip stuck (or open, which floats high on TTL).
-- The chip then sees only one of each pair of addresses that differ in that
-- line, so both addresses of a pair hold the same byte: whichever was
-- written last. Modelled by making every CPU write also land on the partner
-- address, after first giving each pair the contents of the cell the chip
-- would actually use.
P.addr_line_stuck = {
	tier = "A",
	apply = function(engine, p, rec)
		local sp = space(p.space or ":maincpu", p.space_name)
		local s, e = range_of(p)
		local bit = 1 << num(p.line, "line")
		local level = (p.level == "open") and 1 or level_of(p)
		for a = s, e do
			local partner = a ~ bit
			if partner < s or partner > e then
				error(string.format("address line %d pairs 0x%x with 0x%x, outside the range", p.line, a, partner), 0)
			end
		end
		for a = s, e do
			if a & bit == 0 then
				local used = (level == 1) and (a | bit) or a
				local v = sp:read_u8(used)
				self_write(sp, a, v)
				self_write(sp, a | bit, v)
			end
		end
		rec.taps = {
			sp:install_write_tap(s, e, "cabsim_" .. rec.id .. "_w", function(offset, data, m)
				if inside then return nil end
				self_write(sp, offset ~ bit, data)
				return nil
			end),
		}
	end,
}

-- A chip that is never selected. kind = "ram": its cells read as the open
-- bus value (to the CPU and to the video, which read the same chip), writes
-- vanish, and the chip keeps its contents, which come back when the fault
-- clears. kind = "device": reads return open bus; a tap can't cancel a
-- write, so each register write is replaced by the last value written
-- before the fault (from a write watch the timeline or caller started).
-- Known gap: a write to a strobe register still triggers its action.
P.cs_dead = {
	tier = "A",
	apply = function(engine, p, rec)
		local sp = space(p.space or ":maincpu", p.space_name)
		local s, e = range_of(p)
		local open_bus = num(p.open_bus, "open_bus") & 0xff
		local kind = p.kind or "ram"
		if kind == "ram" then
			local saved = sp:read_range(s, e, 8)
			for a = s, e do self_write(sp, a, open_bus) end
			local f = function(offset, data, m)
				if inside then return nil end
				return open_bus
			end
			rec.taps = {
				sp:install_read_tap(s, e, "cabsim_" .. rec.id .. "_r", f),
				sp:install_write_tap(s, e, "cabsim_" .. rec.id .. "_w", f),
			}
			rec.undo = function()
				for a = s, e do self_write(sp, a, saved:byte(a - s + 1)) end
			end
		elseif kind == "device" then
			local held = engine:watched(p.space or ":maincpu", s, e)
			rec.taps = {
				sp:install_read_tap(s, e, "cabsim_" .. rec.id .. "_r", function(offset, data, m)
					if inside then return nil end
					return open_bus
				end),
				sp:install_write_tap(s, e, "cabsim_" .. rec.id .. "_w", function(offset, data, m)
					if inside then return nil end
					return held[offset] or 0
				end),
			}
		else
			error("cs_dead kind must be \"ram\" or \"device\"", 0)
		end
	end,
}

-- A register that returns wrong values on read (a failing chip output).
-- rule: {constant = v} | {and_mask = m} | {or_mask = m} | {xor = m}
P.reg_read_override = {
	tier = "A",
	apply = function(engine, p, rec)
		local sp = space(p.space or ":maincpu", p.space_name)
		local addr = num(p.addr, "addr")
		local rule = p.rule or {}
		local fn
		if rule.constant ~= nil then
			local c = num(rule.constant, "constant") & 0xff
			fn = function(d) return c end
		elseif rule.and_mask ~= nil then
			local m = num(rule.and_mask, "and_mask")
			fn = function(d) return d & m end
		elseif rule.or_mask ~= nil then
			local m = num(rule.or_mask, "or_mask")
			fn = function(d) return (d | m) & 0xff end
		elseif rule.xor ~= nil then
			local m = num(rule.xor, "xor")
			fn = function(d) return (d ~ m) & 0xff end
		else
			error("rule needs constant, and_mask, or_mask or xor", 0)
		end
		rec.taps = {
			sp:install_read_tap(addr, addr, "cabsim_" .. rec.id .. "_r", function(offset, data, m)
				if inside then return nil end
				return fn(data)
			end),
		}
	end,
}

-- One bit of a ROM flipped. offset is relative to the region.
P.rom_bit_flip = {
	tier = "A",
	apply = function(engine, p, rec)
		local r = region(p.region or ":maincpu")
		local off = num(p.offset, "offset")
		local mask = 1 << num(p.bit, "bit")
		local old = r:read_u8(off)
		r:write_u8(off, old ~ mask)
		rec.undo = function() r:write_u8(off, old) end
	end,
}

-- A whole ROM chip dead: its bytes read as the open bus value.
P.rom_dead = {
	tier = "A",
	apply = function(engine, p, rec)
		local r = region(p.region or ":maincpu")
		local s, e = range_of(p)
		local open_bus = num(p.open_bus, "open_bus") & 0xff
		local saved = {}
		for off = s, e do
			saved[off] = r:read_u8(off)
			r:write_u8(off, open_bus)
		end
		rec.undo = function()
			for off = s, e do r:write_u8(off, saved[off]) end
		end
	end,
}

-- A lost or stuck interrupt: the CPU's input line is held clear or asserted
-- whatever the driver does (needs patches/0004).
local function irq(mode)
	return {
		tier = "A",
		apply = function(engine, p, rec)
			local dev = device(p.cpu or ":maincpu")
			local line = num(p.line or 0, "line")
			dev:set_input_line_override(line, mode)
			rec.undo = function() dev:set_input_line_override(line, nil) end
		end,
	}
end
P.irq_missing = irq("clear")
P.irq_stuck = irq("assert")

-- A device running at the wrong speed (a drifting crystal or divider).
P.clock_scale = {
	tier = "A",
	apply = function(engine, p, rec)
		local dev = device(p.device or ":maincpu")
		local factor = tonumber(p.factor)
		if not factor or factor <= 0 then error("factor must be greater than zero", 0) end
		local old = dev.clock_scale
		dev.clock_scale = factor
		rec.undo = function() dev.clock_scale = old end
	end,
}

-- Input faults act in the plugin's input layer, which every injected input
-- passes through, and on MAME's own analog reverse setting for OS input.
-- mode: "inverted" | "dead" | "stuck" (buttons: held down) | "noisy"
local function input_fault(mode)
	return {
		tier = "A",
		apply = function(engine, p, rec)
			local port = p.port
			local field_name = p.field
			if not port or not field_name then error("port and field are required", 0) end
			local seed = num(p.seed or 1, "seed")
			rec.input = {port = port, field = field_name, mode = mode, state = seed}
			if mode == "inverted" then
				local fld = engine:field(port, field_name)
				if fld.is_analog then
					local before = fld.analog_reverse
					fld:set_analog_reverse(not before)
					rec.undo = function() fld:set_analog_reverse(before) end
				end
			end
		end,
	}
end
P.input_inverted = input_fault("inverted")
P.input_dead = input_fault("dead")
P.input_stuck = input_fault("stuck")
P.input_noisy = input_fault("noisy")

-- A sync or video-timing line stuck: rows of the exported frame are
-- remapped as if one bit of the vertical counter were forced
-- (out[y] = in[y with the bit forced]). This is Tier B: MAME draws the
-- picture functionally, so the remap is applied to the frame the plugin
-- exports, not inside the emulated video hardware. An optional irq
-- ("missing" or "stuck") lowers the same line's effect on the CPU, which is
-- Tier A.
P.sync_timing = {
	tier = "B",
	apply = function(engine, p, rec)
		local bit = 1 << num(p.line_bit, "line_bit")
		local level = level_of(p)
		local offset = num(p.first_line or 0, "first_line")
		rec.video = function(pixels, width, height)
			local stride = width * 4
			local rows = {}
			for y = 0, height - 1 do
				local v = y + offset
				local src = (level == 1) and (v | bit) or (v & ~bit)
				src = src - offset
				if src < 0 or src >= height then
					rows[#rows + 1] = string.rep("\0", stride)
				else
					rows[#rows + 1] = pixels:sub(src * stride + 1, (src + 1) * stride)
				end
			end
			return table.concat(rows)
		end
		if p.irq == "missing" or p.irq == "stuck" then
			local sub = {}
			P["irq_" .. p.irq].apply(engine, {cpu = p.cpu, line = p.irq_line}, sub)
			rec.undo = sub.undo
			rec.tier = "B+A"
		end
	end,
}

M.primitives = P

-- ------------------------------------------------------------------- engine

function M.new()
	local self = setmetatable({}, Engine)
	self.faults = {}      -- id -> record
	self.order = {}       -- ids in apply order
	self.next_id = 1
	self.watches = {}     -- key -> {space, start, end, values, tap}
	self.inputs = {}      -- "port|field" -> {position}
	return self
end

function Engine:field(port, field_name)
	local p = manager.machine.ioport.ports[port]
	if not p then error("no input port " .. tostring(port), 0) end
	local f = p.fields[field_name]
	if not f then error("port " .. port .. " has no field " .. tostring(field_name), 0) end
	return f
end

-- Start recording writes to a range, so cs_dead on a device can hold the
-- values its registers had before the fault.
function Engine:watch_writes(space_tag, s, e)
	local key = space_tag .. ":" .. s .. "-" .. e
	local w = self.watches[key]
	if w and w.tap then return w end
	w = w or {space = space_tag, start = s, ["end"] = e, values = {}}
	local sp = space(space_tag)
	w.tap = sp:install_write_tap(s, e, "cabsim_watch_" .. s, function(offset, data, m)
		if not inside then w.values[offset] = data end
		return nil
	end)
	self.watches[key] = w
	return w
end

function Engine:watched(space_tag, s, e)
	for _, w in pairs(self.watches) do
		if w.space == space_tag and w.start <= s and w["end"] >= e then
			local copy = {}
			for k, v in pairs(w.values) do copy[k] = v end
			return copy
		end
	end
	return {}
end

local function install(self, rec)
	local def = P[rec.primitive]
	rec.taps, rec.undo, rec.video, rec.input = nil, nil, nil, nil
	rec.tier = def.tier
	def.apply(self, rec.params, rec)
end

function Engine:apply(primitive, params)
	local def = P[primitive]
	if not def then error("unknown primitive " .. tostring(primitive), 0) end
	local rec = {id = self.next_id, primitive = primitive, params = params or {}}
	install(self, rec)
	self.next_id = self.next_id + 1
	self.faults[rec.id] = rec
	self.order[#self.order + 1] = rec.id
	return rec.id, rec.tier
end

local function uninstall(rec)
	for _, t in ipairs(rec.taps or {}) do t:remove() end
	rec.taps = nil
	if rec.undo then rec.undo() end
	rec.undo = nil
end

function Engine:clear(id)
	local rec = self.faults[id]
	if not rec then return false end
	uninstall(rec)
	self.faults[id] = nil
	for i, v in ipairs(self.order) do
		if v == id then table.remove(self.order, i) break end
	end
	return true
end

function Engine:clear_all()
	local n = 0
	for i = #self.order, 1, -1 do
		if self:clear(self.order[i]) then n = n + 1 end
	end
	return n
end

function Engine:list()
	local out = {}
	for _, id in ipairs(self.order) do
		local r = self.faults[id]
		out[#out + 1] = {id = id, primitive = r.primitive, params = r.params, tier = r.tier}
	end
	return out
end

-- Called when a new machine starts after a hard reset: device objects,
-- spaces and regions are new, so taps, watches and overrides are put back.
function Engine:on_machine_start()
	for _, w in pairs(self.watches) do
		w.tap = nil
		self:watch_writes(w.space, w.start, w["end"])
	end
	for _, id in ipairs(self.order) do
		local rec = self.faults[id]
		rec.taps, rec.undo = nil, nil
		install(self, rec)
	end
end

-- The frame the plugin exports, with every active video fault applied.
function Engine:export_frame(pixels, width, height)
	for _, id in ipairs(self.order) do
		local v = self.faults[id].video
		if v then pixels = v(pixels, width, height) end
	end
	return pixels
end

-- Input layer. Every injected input goes through here, so input faults act
-- on it before the game sees it.
local function input_faults(self, port, field_name)
	local out = {}
	for _, id in ipairs(self.order) do
		local inp = self.faults[id].input
		if inp and inp.port == port and inp.field == field_name then out[#out + 1] = inp end
	end
	return out
end

function Engine:analog_delta(port, field_name, delta)
	local fld = self:field(port, field_name)
	for _, inp in ipairs(input_faults(self, port, field_name)) do
		if inp.mode == "inverted" then
			delta = -delta
		elseif inp.mode == "dead" or inp.mode == "stuck" then
			delta = 0
		elseif inp.mode == "noisy" then
			inp.state = (inp.state * 1103515245 + 12345) & 0x7fffffff
			delta = delta + ((inp.state >> 16) % 5) - 2
		end
	end
	local key = port .. "|" .. field_name
	local st = self.inputs[key]
	if not st then
		st = {position = fld.defvalue or 0}
		self.inputs[key] = st
	end
	local span = (fld.maxvalue or 255) - (fld.minvalue or 0) + 1
	st.position = (fld.minvalue or 0) + ((st.position + delta - (fld.minvalue or 0)) % span)
	fld:set_value(st.position)
	return st.position
end

function Engine:button(port, field_name, down)
	local fld = self:field(port, field_name)
	for _, inp in ipairs(input_faults(self, port, field_name)) do
		if inp.mode == "dead" then down = false end
		if inp.mode == "stuck" then down = true end
	end
	fld:set_value(down and 1 or 0)
	return down
end

return M
