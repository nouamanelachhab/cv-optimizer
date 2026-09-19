# -*- coding: utf-8 -*-
"""Red-team CV generator: internal tool to audit your own ATS pipeline.

This package builds "adversarial" test CVs by injecting the full text of a
job description into a copy of a real CV, using one of several well-known
content-hiding techniques (white text, tiny font, off-page position,
transparent/invisible text, hidden PDF layers, metadata stuffing).

The goal is purely defensive: it lets you verify whether *your own* ATS text
extractor is fooled by these tricks, so you can harden it. It must never be
used to submit adversarial documents to a real employer -- that would be
resume fraud.
"""
