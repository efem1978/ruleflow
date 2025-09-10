#!/usr/bin/env python3
import sys
from xml.etree import ElementTree as ET


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "pytest-junit.xml"
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        print(f"[skipxfail] unable to read {path}: {e}")
        return 0
    skipped = 0
    xfails = 0
    for case in root.iter("testcase"):
        for child in list(case):
            tag = child.tag.lower()
            if tag == "skipped":
                skipped += 1
                # Heuristic: xfail often appears in message/text
                text = (child.text or "") + " " + " ".join(child.attrib.values())
                if "xfail" in text.lower():
                    xfails += 1
    print(f"[skipxfail] skipped={skipped} (xfail≈{xfails}) from {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
