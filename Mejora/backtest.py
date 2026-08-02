"""
Catalyst Radar :: backtest hacia adelante.

Lee las fotos acumuladas en token_snapshots y mide, para cada candidato, la
ganancia maxima desde la PRIMERA foto (donde el scorer lo puntuo). Agrega por
bucket de score para responder la pregunta de calibracion: ¿los tickers que
puntuaron alto de verdad se movieron mas que los que puntuaron bajo?

Se llena con el tiempo: cada corrida diaria del radar agrega una foto. Con pocos
dias de datos los numeros no significan nada todavia; la señal aparece cuando
hay varias semanas y eventos que ya pasaron.

Uso:
    python backtest.py
"""
from __future__ import annotations

from store import connect, backtest_summary, snapshot_count


def main() -> None:
    conn = connect()
    n = snapshot_count(conn)
    bt = backtest_summary(conn)
    print(f"== Backtest Catalyst ==")
    print(f"Fotos acumuladas: {n}")
    print(f"Candidatos con >=2 fotos (medibles): {bt['tracked']}")
    if not bt["tracked"]:
        print("\nAun sin datos suficientes. El radar corre 1x/dia; vuelve en unos dias/semanas.")
        return

    def line(label, avg, n):
        v = f"{avg:+.1f}%" if avg is not None else "  —  "
        print(f"  {label:18} {v:>8}   ({n} tokens)")

    print("\nGanancia maxima promedio por bucket de score de entrada:")
    line("score >= 70", bt["avg_gain_70plus"], bt["n_70plus"])
    line("score 50-69", bt["avg_gain_50_69"], bt["n_50_69"])
    line("score < 50", bt["avg_gain_lt50"], bt["n_lt50"])
    print(f"\nScorer {'CALIBRADO (alto > bajo)' if bt['calibrated'] else 'aun sin señal clara'}")

    print("\nTop movimientos registrados:")
    for t in bt["top"][:10]:
        print(f"  {t['max_gain_pct']:>+7.1f}%  score {t['entry_score']:>3}  "
              f"${t['token_symbol']:<10} {t['ip_name'][:34]}")


if __name__ == "__main__":
    main()
