"""Standalone probe for the application entry marking.

Answers one question: why does the include `FAQ_Home = 6 -> Form0:A1_1` fire
while the response carrying the identical guard leaves nothing pending?

Run:  python diagnose_application_entry.py <graph_id>

Uses API_KEY / TOKEN / ROOT_URL from the environment, exactly like app.py.
Creates its own throwaway simulation and never touches a running session.
"""
import json
import os
import sys

import dcr_repository as repo

ENTRY_EVENT = 'FAQ_Home'
ENTRY_VALUE = '6'
FIELD = 'Form0:A1_1'
CONTAINER = 'Form0'


def snapshot(state):
    payload = repo.get_raw_events(state)
    return {e['id']: e for e in payload['events']}, payload


def line(events, eid):
    e = events.get(eid)
    if not e:
        return f'  {eid:22} MISSING FROM PAYLOAD'
    return (f'  {eid:22} included={str(e.get("included")):5} '
            f'enabled={str(e.get("enabled")):5} pending={str(e.get("pending")):5} '
            f'executed={str(e.get("executed")):5}')


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(__doc__)
        return 2
    state = dict(api_key=os.getenv('API_KEY'), token=os.getenv('TOKEN'),
                 root_url=os.getenv('ROOT_URL'), graph_id=sys.argv[1])
    if not state['api_key'] or not state['root_url']:
        print('Set API_KEY, TOKEN and ROOT_URL first.')
        return 2

    state['simulation_id'] = repo.create_simulation(state)
    if not state['simulation_id']:
        print('Could not create a simulation.')
        return 1
    print(f'graph={state["graph_id"]} simulation={state["simulation_id"]}\n')

    events, payload = snapshot(state)

    # 1. Every key the API returns. If a nested/effective pending field exists,
    #    it appears here and the bug is on the read side, not in the graph.
    keys = sorted({k for e in payload['events'] for k in e})
    print('--- 1. keys returned per event ---')
    print(' ', keys, '\n')

    print('--- 2. full raw record for the container and the first field ---')
    for eid in (CONTAINER, FIELD):
        print(f'  {eid}:')
        print('   ', json.dumps(events.get(eid, {}), ensure_ascii=False, indent=2).replace('\n', '\n    '))
    print()

    print('--- 3. before entry ---')
    for eid in (ENTRY_EVENT, CONTAINER, FIELD):
        print(line(events, eid))
    print()

    # 4. First execution. The include and the response share a guard, so both
    #    should fire here. The field is still excluded at this moment.
    if not repo.execute_raw_event(state, ENTRY_EVENT, ENTRY_VALUE):
        print('Entry execution failed.')
        return 1
    events, _ = snapshot(state)
    print(f'--- 4. after first {ENTRY_EVENT}={ENTRY_VALUE} ---')
    for eid in (ENTRY_EVENT, CONTAINER, FIELD):
        print(line(events, eid))
    first_pending = events.get(FIELD, {}).get('pending')
    print()

    # 5. THE TEST. The field is now included. If a response only registers an
    #    active pending on an already-included target, executing the same entry
    #    again will make it pending this time. That result means the response is
    #    being applied to a still-excluded event in the first cycle, and the
    #    same-cycle include does not retroactively activate it.
    if not repo.execute_raw_event(state, ENTRY_EVENT, ENTRY_VALUE):
        print('Second entry execution failed (entry may be one-shot).')
    else:
        events, _ = snapshot(state)
        print(f'--- 5. after second {ENTRY_EVENT}={ENTRY_VALUE} (field already included) ---')
        for eid in (ENTRY_EVENT, CONTAINER, FIELD):
            print(line(events, eid))
        second_pending = events.get(FIELD, {}).get('pending')
        print()
        print('--- verdict ---')
        if first_pending:
            print('  Response fires normally. The failure is elsewhere; compare with a')
            print('  live application session rather than this probe.')
        elif second_pending:
            print('  CONFIRMED: the response only produces an active pending when the')
            print('  target is already included. Ordering inside one execution cycle is')
            print('  the cause, not the subprocess container.')
            print('  Fix in the graph: make the target included before the response can')
            print('  reach it, or drive entry through an event that is already included.')
        else:
            print('  Response never produces a pending on this target, in either cycle.')
            print('  Next: check whether the relation survived import by exporting the')
            print('  graph and searching for a response with targetId="%s".' % FIELD)

    print(f'\nThrowaway simulation {state["simulation_id"]} left in place for inspection.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
