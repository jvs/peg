import importlib
import os
import subprocess

import sourcer


def run(description):
    grammar = sourcer.Grammar(description, include_source=True)

    # Make sure that the grammar describes itself.
    assert grammar.parse(description)

    # Save our current code for meta.py.
    with open('sourcer/meta.py', 'r') as f:
        was = f.read()

    # Replace it with our new code.
    with open('sourcer/meta.py', 'w') as f:
        f.write(f'# Generated by ../{__file__}\n')
        f.write(grammar._source_code)

    # Reload sourcer to load the new code.
    importlib.reload(sourcer)

    # Try parsing the description again, this time using the new code. Then try
    # running the tests.
    try:
        new_grammar = sourcer.Grammar(description, include_source=True)
        assert new_grammar.parse(description)
        subprocess.run('python -m pytest tests', shell=True, check=True)
    except Exception:
        # If we failed, restore the old code and re-raise the exception.
        with open('sourcer/meta.py', 'w') as f:
            f.write(was)
        raise


def read_metasyntax():
    with open(os.path.join(os.path.dirname(__file__), 'metasyntax.txt')) as f:
        return f.read()


if __name__ == '__main__':
    run(read_metasyntax())