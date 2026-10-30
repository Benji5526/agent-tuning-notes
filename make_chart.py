"""실험 결과 차트(results.png)를 만든다. 값은 README 의 실험표와 같다."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

font_manager.fontManager.addfont(r"C:\Windows\Fonts\malgun.ttf")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})

INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
BLUE, LIGHT_BLUE, GRAY = "#2a78d6", "#85b7eb", "#898781"

labels = ["기준선", "실험 1", "실험 2", "실험 3", "실험 4"]
run1 = [59.4, 56.2, 53.1, 68.8, 71.9]
run2 = [56.2, 56.2, 59.4, 62.5, 75.0]

fail_labels = ["근거 표현 누락", "행동 판정", "도구 미호출", "되묻는 문장 아님", "금지 표현"]
before = [10, 5, 4, 2, 1]
after = [5, 6, 3, 1, 0]


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def bars(ax, xs, a, b, ca, cb, la, lb, fmt):
    w = 0.34
    ra = ax.bar([x - w / 2 - 0.01 for x in xs], a, w, color=ca, label=la)
    rb = ax.bar([x + w / 2 + 0.01 for x in xs], b, w, color=cb, label=lb)
    for r in list(ra) + list(rb):
        ax.text(r.get_x() + r.get_width() / 2, r.get_height(), fmt(r.get_height()),
                ha="center", va="bottom", fontsize=9, color=INK)


fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 8.4), constrained_layout=True)
xs = range(len(labels))
bars(a1, xs, run1, run2, BLUE, LIGHT_BLUE, "1회차", "2회차", lambda v: f"{v:.1f}")
a1.set_ylim(40, 80)
a1.set_xticks(list(xs), labels, color=INK)
a1.set_yticks([40, 50, 60, 70, 80], ["40%", "50%", "60%", "70%", "80%"])
a1.set_title("실험별 답변 통과율 (32건)", loc="left", fontsize=13, color=INK)
a1.legend(frameon=False, loc="upper left", ncols=2, labelcolor=MUTED)
style(a1)

xf = range(len(fail_labels))
bars(a2, xf, before, after, GRAY, BLUE, "기준선", "실험 4 이후", lambda v: f"{v:.0f}")
a2.set_ylim(0, 12)
a2.set_xticks(list(xf), fail_labels, color=INK)
a2.set_title("실패 유형별 건수", loc="left", fontsize=13, color=INK)
a2.legend(frameon=False, loc="upper right", ncols=2, labelcolor=MUTED)
style(a2)

fig.savefig("results.png", dpi=160, facecolor="white")
print("saved results.png")
