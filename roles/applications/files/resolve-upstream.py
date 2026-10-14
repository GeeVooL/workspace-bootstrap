"""Resolve official stable download metadata; never install or execute downloads."""
import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Workstation-Bootstrap', 'Accept': '*/*'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def resolve(kind, url, pattern):
    if kind == 'direct':
        return {'url': url, 'checksum': None}
    payload = fetch(url)
    if kind == 'google_page':
        page = payload.decode()
        # Download tables contain the filename and Google's published SHA-256.
        matches = []
        for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', page, re.S | re.I):
            filenames = re.findall(pattern, html.unescape(row))
            checksums = re.findall(r'\b[0-9a-f]{64}\b', row)
            if filenames and checksums:
                filename = filenames[0]
                links = re.findall(r'https://[^\s"<>]+', html.unescape(page))
                links = [link for link in links if urllib.parse.urlparse(link).path.endswith('/' + filename)]
                links = [link for link in links if urllib.parse.urlparse(link).hostname in
                         ('dl.google.com', 'edgedl.me.gvt1.com')]
                if links:
                    matches.append({'url': links[0], 'checksum': 'sha256:' + checksums[0]})
        if not matches:
            raise ValueError('Official Google download table has no matching archive and SHA-256')
        return matches[0]
    if kind == 'google_sdk':
        root = ET.fromstring(payload)
        for element in root.iter():
            element.tag = element.tag.rsplit('}', 1)[-1]
        for package in root.findall('remotePackage'):
            if package.get('path') != pattern or package.find('obsolete') is not None:
                continue
            channel = package.find('channelRef')
            if channel is not None and channel.get('ref') != 'channel-0':
                continue
            for archive in package.findall('./archives/archive'):
                if archive.findtext('host-os') != 'linux':
                    continue
                complete = archive.find('complete')
                checksum = complete.find('checksum')
                algorithm = checksum.get('type', 'sha1')
                digest = checksum.text.strip()
                if algorithm not in ('sha1', 'sha256') or len(digest) != hashlib.new(algorithm).digest_size * 2:
                    raise ValueError('Invalid SDK checksum')
                return {'url': urllib.parse.urljoin(url, complete.findtext('url')),
                        'checksum': algorithm + ':' + digest}
        raise ValueError('No stable Linux SDK archive found')
    if kind == 'github':
        release = json.loads(payload)
        if release.get('draft') or release.get('prerelease'):
            raise ValueError('Expected a stable GitHub release')
        assets = [a for a in release['assets'] if re.fullmatch(pattern, a['name'])]
        if len(assets) != 1:
            raise ValueError('Expected exactly one upstream release asset')
        asset = assets[0]
        digest = asset.get('digest', '')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
            raise ValueError('Upstream release asset lacks a GitHub SHA-256 digest')
        return {'url': asset['browser_download_url'], 'checksum': digest}
    if kind == 'adoptium':
        releases = json.loads(payload)
        package = releases[0]['binary']['package']
        if not re.fullmatch(r'[0-9a-f]{64}', package['checksum']):
            raise ValueError('Invalid Adoptium SHA-256')
        return {'url': package['link'], 'checksum': 'sha256:' + package['checksum']}
    raise ValueError('Unknown metadata source: ' + kind)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['google_page', 'google_sdk', 'github', 'adoptium', 'direct'])
    parser.add_argument('url')
    parser.add_argument('pattern')
    args = parser.parse_args()
    print(json.dumps(resolve(args.kind, args.url, args.pattern)))
