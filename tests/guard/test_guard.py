"""Tests for the guard module (G1-G3 blocking checks)."""

from __future__ import annotations

from pathlib import Path

from src.guard import Operation, RenderedBlock, run_guard
from src.guard.checks import (
    check_g4_dictionary,
    check_g5_grammar,
    check_g6_keyword_density,
    check_g7_entity_casing,
    check_g8_typography,
)

_MINI_DICT_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "mini_fr" / "mini"


def _keep(block_id: str, text: str) -> RenderedBlock:
    return RenderedBlock(
        block_id=block_id,
        operation=Operation.KEEP,
        source_text=text,
        output_text=text,
    )


def _insert(block_id: str, text: str) -> RenderedBlock:
    return RenderedBlock(
        block_id=block_id,
        operation=Operation.INSERT,
        source_text=None,
        output_text=text,
    )


def test_g1_passes_when_keep_block_untouched():
    blocks = [_keep("b1", "Ingénieur diplômé en génie informatique")]
    report = run_guard(blocks)
    assert report.passed
    assert not [f for f in report.findings if f.rule_id == "G1"]


def test_g1_fails_when_keep_block_altered():
    altered = RenderedBlock(
        block_id="b1",
        operation=Operation.KEEP,
        source_text="Développement Oracle PL/SQL (-65% de temps)",
        output_text="Developpement Oracle PL SQL 65% de temps",
    )
    report = run_guard([altered])
    assert not report.passed
    assert any(f.rule_id == "G1" for f in report.errors)


def test_g1_fails_when_insert_block_has_source_text():
    bad = RenderedBlock(
        block_id="b1",
        operation=Operation.INSERT,
        source_text="should not be here",
        output_text="Some validated template sentence.",
    )
    report = run_guard([bad])
    assert not report.passed
    assert any(f.rule_id == "G1" for f in report.errors)


def test_g2_detects_unfilled_placeholder():
    blocks = [_insert("b1", "Expérience en {competence} pendant {duree} ans.")]
    report = run_guard(blocks)
    assert not report.passed
    assert any(f.rule_id == "G2" for f in report.errors)


def test_g2_detects_todo_and_none_and_nan():
    blocks = [
        _insert("b1", "TODO: compléter cette section"),
        _insert("b2", "Salaire souhaité: None"),
        _insert("b3", "Score: nan"),
    ]
    report = run_guard(blocks)
    ids = {f.block_id for f in report.errors if f.rule_id == "G2"}
    assert ids == {"b1", "b2", "b3"}


def test_g2_passes_on_clean_text():
    blocks = [_insert("b1", "Développement d'applications Python et SQL.")]
    report = run_guard(blocks)
    assert report.passed


def test_g3_detects_diacritic_loss():
    blocks = [
        _keep("b1", "Ingénieur diplômé, développement, sécurité, données"),
        RenderedBlock(
            block_id="b2",
            operation=Operation.KEEP,
            source_text="Ingénieur diplômé, développement, sécurité, données",
            output_text="Ingenieur diplome, developpement, securite, donnees",
        ),
    ]
    # Force G1 to be bypassed conceptually: we only care about G3 here, so
    # check findings filtered to G3 regardless of G1 also failing.
    report = run_guard(blocks)
    assert any(f.rule_id == "G3" for f in report.errors)


def test_g3_passes_when_diacritics_preserved():
    blocks = [_keep("b1", "Ingénieur diplômé en génie informatique, sécurité réseau")]
    report = run_guard(blocks)
    assert not any(f.rule_id == "G3" for f in report.errors)


def test_report_passed_true_when_no_errors():
    blocks = [_keep("b1", "texte neutre sans accent")]
    report = run_guard(blocks)
    assert report.passed
    assert report.errors == []


# --- G4: dictionary check ----------------------------------------------


def test_g4_skipped_when_no_dictionary_path():
    blocks = [_insert("b1", "Cette phrase contient zzxxqq un mot inconnu.")]
    findings = check_g4_dictionary(blocks)
    assert findings == []


def test_g4_flags_unknown_lowercase_word():
    blocks = [_insert("b1", "python sql zzxxqq")]
    findings = check_g4_dictionary(blocks, dictionary_path=_MINI_DICT_PATH)
    assert any(f.rule_id == "G4" and "zzxxqq" in f.message for f in findings)


def test_g4_passes_on_known_words():
    blocks = [_insert("b1", "bonjour python sql")]
    findings = check_g4_dictionary(blocks, dictionary_path=_MINI_DICT_PATH)
    assert findings == []


def test_g4_skips_capitalized_words():
    blocks = [_insert("b1", "Decathlon python")]
    findings = check_g4_dictionary(blocks, dictionary_path=_MINI_DICT_PATH)
    assert findings == []


def test_g4_only_checks_insert_blocks():
    blocks = [_keep("b1", "zzxxqq mot inconnu conservé tel quel")]
    findings = check_g4_dictionary(blocks, dictionary_path=_MINI_DICT_PATH)
    assert findings == []


# --- G5: grammar check (optional) ---------------------------------------


def test_g5_skipped_without_client_and_no_local_server():
    blocks = [_insert("b1", "Une phrase quelconque.")]
    findings = check_g5_grammar(blocks)
    assert findings == []


def test_g5_uses_injected_client():
    class FakeMatch:
        message = "Erreur de grammaire simulée"

    class FakeClient:
        def check(self, text):
            return [FakeMatch()]

    blocks = [_insert("b1", "Une phrase quelconque.")]
    findings = check_g5_grammar(blocks, language_tool_client=FakeClient())
    assert len(findings) == 1
    assert findings[0].rule_id == "G5"
    assert findings[0].severity.value == "warning"


# --- G6: keyword density --------------------------------------------------


def test_g6_skipped_without_skill_terms():
    blocks = [_insert("b1", "Python Python Python Python")]
    findings = check_g6_keyword_density(blocks)
    assert findings == []


def test_g6_flags_keyword_stuffing():
    blocks = [_insert("b1", "Python Python Python Python et encore Python.")]
    findings = check_g6_keyword_density(blocks, skill_terms=["Python"], max_occurrences=3)
    assert any(f.rule_id == "G6" for f in findings)


def test_g6_passes_within_limit():
    blocks = [_insert("b1", "Python et SQL, puis encore un peu de Python.")]
    findings = check_g6_keyword_density(blocks, skill_terms=["Python"], max_occurrences=3)
    assert findings == []


# --- G7: entity casing -----------------------------------------------------


def test_g7_skipped_without_proper_nouns():
    blocks = [_insert("b1", "Expérience chez decathlon.")]
    findings = check_g7_entity_casing(blocks)
    assert findings == []


def test_g7_flags_casing_mismatch():
    blocks = [_insert("b1", "Expérience chez decathlon en 2020.")]
    findings = check_g7_entity_casing(blocks, proper_nouns=["Decathlon"])
    assert any(f.rule_id == "G7" for f in findings)


def test_g7_passes_when_casing_preserved():
    blocks = [_insert("b1", "Expérience chez Decathlon en 2020.")]
    findings = check_g7_entity_casing(blocks, proper_nouns=["Decathlon"])
    assert findings == []


def test_g7_only_checks_insert_blocks():
    blocks = [_keep("b1", "Expérience chez decathlon en 2020.")]
    findings = check_g7_entity_casing(blocks, proper_nouns=["Decathlon"])
    assert findings == []


def test_run_guard_threads_g4_g7_context_through():
    blocks = [_insert("b1", "Expérience chez Decathlon avec Python Python Python Python.")]
    report = run_guard(
        blocks,
        dictionary_path=_MINI_DICT_PATH,
        skill_terms=["Python"],
        max_keyword_occurrences=3,
        proper_nouns=["Decathlon"],
    )
    assert any(f.rule_id == "G6" for f in report.errors)


# --- G5: Grammalecte-first preference --------------------------------------


def test_g5_prefers_grammalecte_when_available(monkeypatch):
    import src.guard.checks as checks_module

    def fake_grammalecte_checker():
        return lambda text: ["erreur simulée via Grammalecte"]

    monkeypatch.setattr(checks_module, "_grammalecte_checker", fake_grammalecte_checker)

    class FailingClient:
        def check(self, text):
            raise AssertionError("language_tool_python must not be used when Grammalecte succeeds")

    blocks = [_insert("b1", "Une phrase quelconque.")]
    findings = check_g5_grammar(blocks, language_tool_client=FailingClient())
    assert len(findings) == 1
    assert "Grammalecte" in findings[0].message


def test_g5_falls_back_to_language_tool_when_grammalecte_unavailable(monkeypatch):
    import src.guard.checks as checks_module

    def raising_grammalecte_checker():
        raise ImportError("grammalecte not installed")

    monkeypatch.setattr(checks_module, "_grammalecte_checker", raising_grammalecte_checker)

    class FakeMatch:
        message = "Erreur de grammaire simulée"

    class FakeClient:
        def check(self, text):
            return [FakeMatch()]

    blocks = [_insert("b1", "Une phrase quelconque.")]
    findings = check_g5_grammar(blocks, language_tool_client=FakeClient())
    assert len(findings) == 1
    assert findings[0].rule_id == "G5"


def test_g5_never_checks_keep_blocks():
    blocks = [_keep("b1", "zzxxqq texte original jamais corrigé")]
    findings = check_g5_grammar(blocks, language_tool_client=None)
    assert findings == []


# --- G8: French typography --------------------------------------------------


def test_g8_flags_missing_narrow_nbsp():
    blocks = [_insert("b1", "Score : 90%")]
    findings = check_g8_typography(blocks)
    assert any(f.rule_id == "G8" for f in findings)


def test_g8_passes_with_correct_spacing():
    from src.render.french_typography import apply_french_typography

    text = apply_french_typography("Score : 90%")
    blocks = [_insert("b1", text)]
    findings = check_g8_typography(blocks)
    assert findings == []


def test_g8_only_checks_insert_blocks():
    blocks = [_keep("b1", "Score : 90%")]
    findings = check_g8_typography(blocks)
    assert findings == []
