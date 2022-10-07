# -*- coding: utf-8 -*-

__author__ = "Brett Feltmate"

# Dependencies
import klibs
from klibs import P
from klibs.KLConstants import STROKE_CENTER, TK_MS
from klibs.KLUtilities import deg_to_px
from klibs.KLUserInterface import any_key, ui_request
from klibs.KLKeyMap import KeyMap
from klibs.KLResponseCollectors import KeyPressResponse
from klibs.KLGraphics import KLDraw as kld
from klibs.KLGraphics import fill, blit, flip, clear
from klibs.KLCommunication import message
from klibs.KLEventInterface import TrialEventTicket as ET
import sdl2
from random import shuffle, choice

# Handy constants that prevent typos
WHITE = [255, 255, 255, 255]
CENTRE = 'centre'
RIGHT = 'right'
LEFT = 'left'
OFFSET = "offset"
CUE = 'cue'
BOX = 'box'
TARGET = 'target'
FIX = 'fix'
STROKE_DEFAULT = 'stroke_default'
STROKE_CUE = 'stroke_cue'
X = 'x'
PLUS = '+'
DETECT = 'detect'
LOCALIZE = 'localize'
DISCRIMINATE = 'discriminate'


class PosnerCueingTask(klibs.Experiment):

	def setup(self):

		# Establish condition order
		self.conditions = [DETECT, LOCALIZE, DISCRIMINATE]
		shuffle(self.conditions)

		self.current_condition = None

		# Stimulus sizings
		self.sizes = {
			BOX: deg_to_px(2),
			TARGET: deg_to_px(1),
			FIX: deg_to_px(1.5),
			# default stimulus outline
			STROKE_DEFAULT: [deg_to_px(0.1), WHITE, STROKE_CENTER],
			# increased thickness applied to placeholder when cued
			STROKE_CUE: [deg_to_px(0.2), WHITE, STROKE_CENTER],
			# offset, centre to centre, between fix and placeholders
			OFFSET: deg_to_px(5)
		}

		# Stimulus landmarks
		self.locations = {
			LEFT: [P.screen_c[0] - self.sizes[OFFSET], P.screen_c[1]],  # [x, y]
			CENTRE: P.screen_c,
			RIGHT: [P.screen_c[0] + self.sizes[OFFSET], P.screen_c[1]]
		}

		# Visual assets
		self.stimuli = {
			FIX:
				kld.FixationCross(size=self.sizes[FIX], thickness=self.sizes[STROKE_DEFAULT][0], fill=WHITE),
			LEFT:
				kld.Rectangle(width=self.sizes[BOX], stroke=self.sizes[STROKE_DEFAULT]),
			RIGHT:
				kld.Rectangle(width=self.sizes[BOX], stroke=self.sizes[STROKE_DEFAULT]),
			PLUS:
				kld.FixationCross(size=self.sizes[TARGET], thickness=self.sizes[STROKE_DEFAULT][0], fill=WHITE),
			X:
				kld.FixationCross(size=self.sizes[TARGET], thickness=self.sizes[STROKE_DEFAULT][0], fill=WHITE, rotation=45)
		}

		# Response collector
		self.rc.uses(KeyPressResponse)
		self.rc.keypress_listener.interrupts = True  # end trial upon valid (correct or otherwise) response
		self.rc.terminate_after = [P.response_window, TK_MS]  # Wait this long for response (specified in _params.py)

		# TODO: better name
		# I assume you want key mapping for discriminations counter-balanced; delete call to shuffle() if not
		target_mapping = [X, PLUS]
		shuffle(target_mapping)

		# Response mappings by task demand, assigned to response collector in self.block()
		self.keymaps = {
			LOCALIZE:  # I'm assuming here that you don't want localization key mappings to be randomized
				KeyMap(
					LOCALIZE,
					['z', '/'],  # actual name of the keys to listen for, don't know why this needs specifying
					[LEFT, RIGHT],  # what gets written to the date file
					[sdl2.SDLK_z, sdl2.SDLK_SLASH]  # keycodes corresponding to the desired keys
				),
			DISCRIMINATE:
				KeyMap(
					DISCRIMINATE,
					['z', '/'],
					target_mapping,
					[sdl2.SDLK_z, sdl2.SDLK_SLASH]
				),
			DETECT:
				KeyMap(DETECT, ['spacebar'], [DETECT], [sdl2.SDLK_SPACE])
		}


		# Iterates across message list at beginning of block
		self.instructions = {
			DETECT: ['Page 1 of detect text', 'spacebar is response key', 'Page N of detect text'],
			LOCALIZE: ['Page 1 of localize text', 'z for left, / for right', 'Page N of localize text'],
			DISCRIMINATE: ['Page 1 of discriminate text', 'Z for {0}, and / for {1}'.format(target_mapping[0], target_mapping[1]), 'Page N of discriminate text']
		}

	def block(self):
		# Get condition
		# TODO: Figure out practice blocks
		if self.current_condition is None:
			self.current_condition = self.conditions.pop()

		# Present instructions for task
		for txt in self.instructions[self.current_condition]:
			fill()
			message(txt, location=P.screen_c, registration=5, blit_txt=True)
			flip()
			# wait for key press
			any_key()


	# Before each trial, ensures correct keymapping is set up
	def setup_response_collector(self):
		self.rc.keypress_listener.key_map = self.keymaps[self.current_condition]

	# Set up trial specific properties
	def trial_prep(self):

		# Once response collection begins, self.catch_trial (see _ind_vars.py) determines if target is presented or not
		# Note: currently waits for the entire response period before ending the trial, catch or not.
		self.rc.display_callback = self.present_display

		self.rc.display_kwargs = {'present_target': False if self.catch_trial else True}

		self.ctoa = self.get_ctoa()

		# Define trial event time course
		events = []

		# Present cue SOA ms (see _params.py) after trial init
		events.append([P.fix_cue_soa, 'cue_onset'])

		# Remove cue cue_duration ms (also _params.py) later
		events.append([events[-1][0] + P.cue_duration, 'cue_offset'])

		# Start response period ctoa ms ([-2] == relative to cue_onset) later
		events.append([events[-2][0] + self.ctoa, 'response_period'])

		# Register trial events to event manager (fancy stopwatch)
		for e in events:
			self.evm.register_ticket(ET(e[1], e[0]))


		# Presenting the initial display before the trial 'starts' makes things go smoother
		# Initially presents fixation...
		fill()
		blit(self.stimuli[FIX], location=self.locations[CENTRE], registration=5)
		flip()

		# Following trial init by any key...
		any_key()

		# Placeholders appear. This makes it visually obvious when a new trial starts
		self.present_display()

	def trial(self):

		# Until cue onset, do nothing.
		while self.evm.before('cue_onset'):
			# ui_request() ensures the computer doesn't get locked up (i.e., allows for quitting)
			ui_request()

		# Present cue
		self.present_display(cue_period=True)

		# Wait to remove
		while self.evm.before('cue_offset'):
			ui_request()

		# Remove cue
		self.present_display(cue_period=False)

		# Wait to present target (or not)
		while self.evm.before('response_period'):
			ui_request()

		# Enter response collection phase, which handles target presentation
		self.rc.collect()
		# Returns ['NO_RESPONSE', -1] following timeout
		response = self.rc.keypress_listener.response()

		return {
			"block_num": P.block_number,
			"trial_num": P.trial_number,
			"response_condition": self.current_condition,
			"catch_trial": self.catch_trial,
			"ctoa": self.ctoa,
			"cue_loc": self.cue_loc,
			"target_loc": 'CATCH' if self.catch_trial else self.target_loc,
			"target_type": 'CATCH' if self.catch_trial else self.target_type,
			"response": response.value,
			"rt": response.rt
		}

	def trial_clean_up(self):
		clear()

		self.rc.keypress_listener.reset()
		if P.trial_number == P.trials_per_block:
			self.current_condition = None


	def clean_up(self):
		pass

	def present_display(self, cue_period=False, present_target=False):
		fill()

		# If cue period, widen cue box; otherwise ensure all are normal width
		if cue_period:
			self.stimuli[self.cue_loc].stroke = self.sizes[STROKE_CUE]
		else:
			self.stimuli[self.cue_loc].stroke = self.sizes[STROKE_DEFAULT]

		# Present the things
		blit(self.stimuli[LEFT], location=self.locations[LEFT], registration=5)
		blit(self.stimuli[FIX], location=self.locations[CENTRE], registration=5)
		blit(self.stimuli[RIGHT], location=self.locations[RIGHT], registration=5)

		# Additionally present target during target period
		if present_target:
			blit(self.stimuli[self.target_type], location=self.locations[self.target_loc], registration=5)

		flip()

	# Selects CTOA from range min:max, taking into account refresh
	def get_ctoa(self, low=100, high=1000):
		min_flips = int(round(low / P.refresh_time))
		max_flips = int(round(high / P.refresh_time))

		soa = choice(range(min_flips, max_flips + 1)) * P.refresh_time

		return soa

