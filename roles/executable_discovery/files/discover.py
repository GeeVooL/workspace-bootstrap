"""Read-only executable discovery for local workstation playbooks."""
import json
import os
import re
import subprocess
import sys


def discover(spec):
    commands = spec['commands']
    if not commands or any('/' in name or not name for name in commands):
        raise ValueError('commands must contain executable names, not paths')
    directories = [p for p in spec['search_path'].split(os.pathsep) if os.path.isabs(p)]
    override = spec.get('override', '')
    if override and not os.path.isabs(override):
        raise ValueError('executable overrides must be absolute paths')
    if override and os.path.basename(override) != commands[0]:
        raise ValueError('an override must use the primary command filename so shells resolve the same executable')
    # Keep invocation paths: resolving a rustup-style proxy changes argv[0].
    paths = ([override] if override else
             [os.path.join(directory, name) for name in commands for directory in directories]
             + spec.get('paths', []))
    candidates, occupied, seen = [], [], set()
    for path in paths:
        if not os.path.isabs(path):
            raise ValueError('known executable paths must be absolute')
        if not os.path.lexists(path):
            continue
        if not os.path.isfile(path) or not os.access(path, os.X_OK):
            occupied.append(path)
            continue
        identity = os.path.realpath(path)
        if identity not in seen:
            candidates.append(path)
            seen.add(identity)
    result = {'status': 'missing', 'path': '', 'candidates': candidates,
              'reason': 'no installation found'}
    if not candidates:
        if occupied or override:
            result.update(status='broken', path=override or occupied[0],
                          reason='configured or existing path is not an executable regular file')
        return result
    result['path'] = candidates[0]
    if override:
        for directory in directories:
            visible = os.path.join(directory, commands[0])
            if os.path.isfile(visible) and os.access(visible, os.X_OK):
                if os.path.realpath(visible) != os.path.realpath(override):
                    result.update(status='conflict', reason=f'PATH selects {visible} before the override; align the search path and override directories')
                    return result
                break
    try:
        probe = subprocess.run([result['path'], *spec.get('probe', ['--version'])],
                               env=dict(os.environ, PATH=spec['search_path']),
                               cwd='/', capture_output=True, text=True, errors='replace', timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        result.update(status='broken', reason=str(error))
        return result
    if probe.returncode:
        result.update(status='broken', reason=f'version probe exited with status {probe.returncode}')
        return result
    minimum = spec.get('minimum_version', '')
    match = re.search(spec.get('version_pattern', r'\d+\.\d+(?:\.\d+)?'), probe.stdout + '\n' + probe.stderr)
    result['version'] = match.group(0) if match else ''
    if not match:
        result.update(status='broken', reason='version probe did not identify a version')
        return result
    if minimum:
        def version(value):
            return tuple(int(n) for n in (value.split('.') + ['0', '0'])[:3])
        if version(result['version']) < version(minimum):
            result.update(status='incompatible', reason=f'version {result["version"]} is below required {minimum}')
            return result
    result.update(status='ready', reason='reusing existing installation')
    return result


if __name__ == '__main__':
    print(json.dumps(discover(json.loads(sys.argv[1]))))
