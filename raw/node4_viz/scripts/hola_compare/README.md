# HOLA vs ELK — throwaway comparison (2026-09-07)

    python3 -m venv .venv && .venv/bin/pip install hola-graph     # builds Adaptagrams from source (~3 min)
    .venv/bin/python hola_run.py hood_04 hood_04_wide               # -> *_hola.svg / *_hola.json
    node svg2png.mjs hood_04_hola hood_04_wide_hola                 # -> PNGs (uses the app's playwright)

Inputs are `/api/neighborhood` dumps for `ankitha_1/04_build_accounts.sas` (up=1,down=1 and up=3,down=3).
Result pictures: `../../../plots/hola_ankitha_04*.png`. Verdict in the exp_003 wiki, bronze run page.
