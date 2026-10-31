"""Deterministic raw ACT stepping and pinned Korangar timing; no clock or fallback."""
from __future__ import annotations

import copy
import math
import struct
import sys

from ro_sprite_forge.core.canonical import canonical_bytes, digest, check, sealed
from ro_sprite_forge.core.contracts import frozen_runtime_profile

TIMING_VERSION = "1.0.0"
UINT32_MAX = 2**32 - 1


def _f32(value: float) -> float:
    check(math.isfinite(value) and abs(value) <= 3.4028234663852886e38,
          "Timing value exceeds finite f32 range.")
    return struct.unpack('<f', struct.pack('<f', value))[0]


def _integer(value, name: str, low: int = 0, high: int = UINT32_MAX) -> int:
    check(type(value) is int and low <= value <= high, f"{name}: expected integer in [{low}, {high}].")
    return value


class AnimationTimeline:
    """Snapshot of decoded ACT motions and an evidence-backed runtime profile.

    Numeric selection always addresses raw motions. Unknown timing remains unresolved.
    No empty motion is omitted and no modulo resource fallback is permitted.
    """

    def __init__(self, act: dict, *, category: str = 'unverified', profile=None):
        check(category in ('player', 'npc', 'monster', 'unverified'), "Unknown actor category.")
        self._act = copy.deepcopy(act)
        self._resource = digest(canonical_bytes(act))
        self._profile = (profile or frozen_runtime_profile(category)).to_dict()
        check(self._profile['category'] == category, 'Runtime profile/category mismatch.')
        self._category = category
        frozen = frozen_runtime_profile(category).to_dict()
        self._pinned = self._profile == frozen

    def select(self, *, action: str | None = None, slot: int | None = None,
               view: int = 0, direction: int | None = None, camera_direction: int = 0,
               frame: int = 0) -> dict:
        _integer(view, 'view', 0, 7)
        _integer(camera_direction, 'camera_direction', 0, 7)
        if direction is not None:
            _integer(direction, 'direction', 0, 7)
            check(view == 0, 'Use view or direction, not both.')
            view = (direction + camera_direction) & 7
        check((action is None) != (slot is None), 'Select exactly one semantic action or numeric ACT slot.')
        if action is not None:
            mapping = next((item for item in self._profile['actions'] if item['id'] == action), None)
            check(mapping is not None and mapping['mapping'] == 'SUPPORTED', f"ACTION_UNSUPPORTED: {action}.")
            slot = mapping['slots'][view]
        else:
            _integer(slot, 'slot')
            check(slot % 8 == view, 'Numeric slot/view mismatch; declare the actual ACT view.')
            mapping = next((item for item in self._profile['actions'] if slot in item['slots'] and item['mapping'] == 'SUPPORTED'), None)
            action = mapping['id'] if mapping else None
        check(slot < len(self._act['actions']), f'ACTION_UNSUPPORTED: slot {slot}; fallback rejected.')
        motions = self._act['actions'][slot]
        check(bool(motions), f'Empty action slot {slot}.')
        _integer(frame, 'frame', 0, len(motions) - 1)
        delay = self._act['delays'][slot] if slot < len(self._act.get('delays', [])) else None
        check(delay is None or (type(delay) in (int, float) and abs(delay) <= 3.4028234663852886e38
                               and math.isfinite(delay)),
              f'Slot {slot} has nonfinite ACT delay.')
        return sealed({
            'schema': 'rsf.timeline-selection/v1', 'timing_version': TIMING_VERSION,
            'act_document_sha256': self._resource,
            'profile_sha256': self._profile['canonical_sha256'], 'category': self._category,
            'action': action, 'requested_slot': slot, 'resolved_slot': slot,
            'view': view, 'direction': direction, 'camera_direction': camera_direction,
            'frame': frame, 'frame_count': len(motions), 'source_delay': delay,
            'mode': 'MANUAL', 'timing_status': 'NOT_EVALUATED', 'timing_rule': None,
            'elapsed_ms': None, 'speed': None, 'context': {}, 'frame_time': None,
            'frame_duration_ms': None, 'looping': None, 'terminal_hold': None,
            'native_completion': None, 'fallback': 'NONE',
            'reachability': mapping['reachability'] if mapping else 'UNVERIFIED',
            'diagnostics': self._limitations(slot),
        })

    def _limitations(self, slot):
        return (['RAW_MOTION_PREPARATION_PARITY_UNVERIFIED: zero-clip ACT motions are retained.']
                if any(not m['clips'] for m in self._act['actions'][slot]) else [])

    def step(self, selection: dict, delta: int, *, loop: bool = False) -> dict:
        _integer(delta, 'step', -UINT32_MAX)
        check(type(loop) is bool, 'loop: expected boolean.')
        base = self._selection(selection)
        requested = base['frame'] + delta
        index = requested % base['frame_count'] if loop else max(0, min(requested, base['frame_count'] - 1))
        return self.select(slot=base['resolved_slot'], view=0 if base['direction'] is not None else base['view'],
                           direction=base['direction'], camera_direction=base['camera_direction'], frame=index)

    def _selection(self, selection):
        # Revalidate derived fields rather than trusting an arbitrary selection record.
        from ro_sprite_forge.core.canonical import check_seal
        check_seal(selection, 'rsf.timeline-selection/v1')
        check(all(key in selection for key in ('act_document_sha256', 'profile_sha256', 'resolved_slot', 'requested_slot', 'view', 'direction', 'camera_direction', 'frame', 'frame_count', 'source_delay')),
              'Incomplete timeline selection.')
        check(selection['act_document_sha256'] == self._resource, 'Selection/ACT identity mismatch.')
        check(selection['profile_sha256'] == self._profile['canonical_sha256'], 'Selection/profile mismatch.')
        fresh = self.select(slot=selection['resolved_slot'], view=0 if selection['direction'] is not None else selection['view'],
                            direction=selection['direction'], camera_direction=selection['camera_direction'], frame=selection['frame'])
        check(fresh['view'] == selection['view'] and fresh['requested_slot'] == selection['requested_slot'],
              'Selection action/view identity mismatch; fallback rejected.')
        check(fresh['frame_count'] == selection['frame_count'] and fresh['source_delay'] == selection['source_delay'],
              'Stale selection/resource mismatch.')
        check(selection.get('mode') in ('MANUAL', 'TIMED'), 'Invalid selection mode.')
        expected = fresh
        if selection['mode'] == 'TIMED':
            check(all(key in selection for key in ('elapsed_ms', 'speed', 'context', 'timing_status',
                                                  'frame_duration_ms', 'looping')),
                  'Incomplete timed selection.')
            context = selection['context']
            check(type(context) is dict, 'Invalid timing context.')
            diagnostic = selection['timing_status'] == 'DIAGNOSTIC'
            if diagnostic:
                check(selection['frame_duration_ms'] is not None, 'Missing diagnostic interval.')
            # Replay only declared inputs. A digest proves integrity, not the truth of
            # derived action/timing/fallback metadata. The recursive validation in
            # seek sees a fresh MANUAL record and terminates here.
            expected = self.seek(fresh, selection['elapsed_ms'], speed=selection['speed'],
                                 movement_speed=context.get('movement_speed'),
                                 duration_ms=context.get('duration_ms'),
                                 diagnostic_frame_ms=selection['frame_duration_ms'] if diagnostic else None,
                                 diagnostic_loop=selection['looping'] if diagnostic else True)
        check(canonical_bytes(selection) == canonical_bytes(expected),
              'Selection metadata does not match source/profile/timing inputs.')
        return fresh

    def seek(self, selection: dict, elapsed_ms: int, *, speed: float = 1.0,
             movement_speed: int | None = None, duration_ms: int | None = None,
             diagnostic_frame_ms: float | None = None, diagnostic_loop: bool = True) -> dict:
        base = self._selection(selection)
        _integer(elapsed_ms, 'elapsed_ms')
        check(type(speed) in (int, float) and 0 < speed <= sys.float_info.max,
              'speed: expected positive finite multiplier.')
        scaled = elapsed_ms * speed
        check(0 <= scaled <= UINT32_MAX, 'Scaled elapsed time exceeds u32 range.')
        tick = int(scaled)  # explicit preview speed; integer runtime simulation tick
        if movement_speed is not None:
            _integer(movement_speed, 'movement_speed', 1)
        if duration_ms is not None:
            _integer(duration_ms, 'duration_ms', 1)
        action = base['action']
        interval = None
        looping = action in ('Idle', 'Walk')
        context = {}
        diagnostics = list(base['diagnostics'])
        rule = None
        timing_status = 'SUPPORTED'
        if diagnostic_frame_ms is not None:
            check(type(diagnostic_frame_ms) in (int, float) and 0 < diagnostic_frame_ms <= sys.float_info.max,
                  'diagnostic_frame_ms: expected positive finite interval.')
            check(type(diagnostic_loop) is bool, 'diagnostic_loop: expected boolean.')
            interval = diagnostic_frame_ms
            diagnostic_time = tick / interval
            check(math.isfinite(diagnostic_time) and diagnostic_time <= UINT32_MAX,
                  'Diagnostic frame time exceeds u32 inspection budget.')
            frame_time = int(diagnostic_time)
            looping = diagnostic_loop
            rule = 'EXPLICIT_DIAGNOSTIC_INTERVAL'
            timing_status = 'DIAGNOSTIC'
            diagnostics.append('DIAGNOSTIC_TIMING: does not establish runtime playback semantics.')
        elif not self._pinned or action not in ('Idle', 'Walk', 'Pickup', 'Attack1', 'Attack3', 'Hurt', 'Die'):
            timing_status = 'UNVERIFIED'
            diagnostics.append('TIMING_UNRESOLVED: no supported pinned state setter for this action/profile.')
            frame_time = None
            looping = None
        elif action in ('Attack1', 'Attack3', 'Hurt'):
            if duration_ms is None:
                timing_status = 'UNVERIFIED'
                diagnostics.append('TIMING_UNRESOLVED: explicit duration_ms required.')
                frame_time = None
            else:
                _integer(duration_ms, 'duration_ms', 1)
                check(tick * base['frame_count'] <= UINT32_MAX, 'Runtime elapsed*frame_count u32 overflow is unsupported.')
                frame_time = tick * base['frame_count'] // duration_ms
                interval = duration_ms / base['frame_count']
                context['duration_ms'] = duration_ms
                rule = 'EXTERNAL_DURATION_U32'
        else:
            delay = base['source_delay']
            check(delay is not None and delay > 0, 'ACT delay must be positive for delay-based timing.')
            factor = 25.0 if action == 'Pickup' else 50.0
            if action == 'Walk':
                if movement_speed is None:
                    timing_status = 'UNVERIFIED'
                    diagnostics.append('TIMING_UNRESOLVED: explicit movement_speed required.')
                    frame_time = None
                else:
                    _integer(movement_speed, 'movement_speed', 1)
                    factor = _f32(_f32(_f32(_f32(float(movement_speed)) * 100.0) / 150.0) / 5.0)
                    context['movement_speed'] = movement_speed
            if timing_status == 'SUPPORTED':
                interval = _f32(_f32(delay) * factor)
                check(interval > 0, 'ACT timing interval underflows f32.')
                frame_time = min(UINT32_MAX, int(_f32(_f32(float(tick)) / interval)))
                rule = 'ACT_DELAY_F32'
        result = {k: v for k, v in base.items() if k != 'canonical_sha256'}
        if frame_time is not None:
            index = frame_time % base['frame_count'] if looping else min(frame_time, base['frame_count'] - 1)
            if timing_status == 'SUPPORTED' and self._category == 'player' and action == 'Idle':
                index = 0
                rule = 'PLAYER_IDLE_FRAME_ZERO'
            result['frame'] = index
        result.update(mode='TIMED', timing_status=timing_status, timing_rule=rule,
                      elapsed_ms=elapsed_ms, speed=speed, context=context, frame_time=frame_time,
                      frame_duration_ms=interval, looping=looping,
                      terminal_hold=(frame_time >= base['frame_count'] if frame_time is not None and not looping else False if frame_time is not None else None),
                      native_completion=None, diagnostics=diagnostics)
        # Native completion evaluates view 0, which may have a different motion count.
        if timing_status == 'SUPPORTED' and not looping and frame_time is not None:
            view_zero = base['resolved_slot'] - base['view']
            if view_zero < len(self._act['actions']) and self._act['actions'][view_zero]:
                completion_selection = self.select(slot=view_zero, view=0)
                count0 = completion_selection['frame_count']
                if rule == 'EXTERNAL_DURATION_U32':
                    check(tick * count0 <= UINT32_MAX, 'Completion elapsed*frame_count overflow.')
                    time0 = tick * count0 // duration_ms
                else:
                    delay0 = completion_selection['source_delay']
                    check(delay0 is not None and delay0 > 0, 'View-zero completion delay is invalid.')
                    interval0 = _f32(_f32(delay0) * (25.0 if action == 'Pickup' else 50.0))
                    check(interval0 > 0, 'Completion interval underflows f32.')
                    time0 = min(UINT32_MAX, int(_f32(_f32(float(tick)) / interval0)))
                result['native_completion'] = time0 > count0
        return sealed(result)
