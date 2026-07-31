# Хэрэглээний үнийн индекс (CPI) тооцоолуур

**Суурь жил: 2023 = 100**

Монгол Улсын ҮСХ-ийн аймаг/нийслэлийн үнийн индекс тооцох Excel (`cpi calculation 2023=100.xlsx`)‑ийн томьёог Python‑д шилжүүлсэн програм.

Аймгуудын **бараа бүтээгдэхүүн бүрийн сарын дундаж үнэ**-г оруулахад:

1. Барааны (elementary) индекс  
2. COICOP бүлгийн индекс  
3. Аймгийн ерөнхий индекс  
4. **Улсын** жигнэсэн индекс (`base index national`)

автоматаар бодогдоно.

## Аргачлал

| Алхам | Томьёо |
|--------|--------|
| Суурь үнэ | \(P_0 = \mathrm{avg}(P_{2023.01},\ldots,P_{2023.12})\) |
| Эхний сар | \(I_t = (P_t / P_0) \times 100\) |
| Дараагийн сар (chain) | \(I_t = (P_t / P_{t-1}) \times I_{t-1}\) |
| Бүлэг / анги | \(I = \sum_i (w_i \cdot I_i) / w_{\mathrm{parent}}\) |
| Улс | \(I^{\mathrm{nat}} = \sum_a (H_a \cdot I_a) / \sum_a H_a\) |

- **Жин (H)** — өрхийн хэрэглээний судалгаанаас (аймаг бүрт өөр)  
- **Харьцангуй жин** — \(w_i = H_i / H_{\mathrm{total}} \times 100\)  
- Үнэ байхгүй/0 бол тухайн барааны индекс = 100 (Excel‑ийн `IF`‑тэй ижил)

> **Бүсчилсэн** тооцоо (баруун/хангай/төв/зүүн…) — дараагийн шатанд нэмэгдэнэ.

## Excel файлын бүтэц

| Sheet | Агуулга |
|-------|---------|
| `01` … `22` | 21 аймаг + Улаанбаатар (`20`) |
| `base index national` | Улсын жигнэсэн индекс |

Sheet дотор:

- **Мөр 8–723** — COICOP шатлал + индекс  
- **Мөр ~728–1443** — сарын дундаж **үнэ** (index мөр + 720)  
- **Багана H** — жин, **K+** — сар (2023.01 …)

## Суулгах

```bash
cd cpi-calculator
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

## Ашиглах

### 1) Командын мөр

```bash
# Бүрэн тооцоо → output/
python cli.py calculate -i "C:\Users\...\cpi calculation 2023=100.xlsx" -o output --json

# Зөвхөн зарим аймаг
python cli.py calculate -i file.xlsx --aimag 01 20 19

# Excel-ийн хадгалагдсан утгатай харьцуулах
python cli.py validate -i file.xlsx
```

Гаралт:

- `output/cpi_result.xlsx` — улс, аймаг, бүлэг, инфляц  
- `output/cpi_overall.csv` — ерөнхий индекс  
- `output/cpi_result.json` — ( `--json` )

### 2) Веб интерфэйс (Streamlit)

```bash
streamlit run app.py
```

Хөтөч дээр Excel upload хийгээд **Тооцоолох**.

## Төслийн бүтэц

```
cpi-calculator/
├── app.py              # Streamlit UI
├── cli.py              # командын мөр
├── requirements.txt
├── cpi/
│   ├── loader.py       # Excel уншигч
│   ├── engine.py       # индекс + улсын жигнэлт
│   └── export.py       # xlsx / json / csv
└── data/
    ├── structure.json  # COICOP шатлал (томьёоноос)
    ├── aimags.json
    └── months.json
```

## GitHub

```bash
git init
git add .
git commit -m "CPI calculator 2023=100 — aimag to national"
gh repo create cpi-calculator --public --source=. --remote=origin --push
```

## Тусгай барааны бүлэг + бүс (`Бүлэг.xlsx`)

`Бүлэг.xlsx` файлын 3 sheet-ийг ашиглана:

| Sheet | Зориулалт |
|-------|-----------|
| **барааны бүлэг** | дотоод, импорт, мах, бараа/үйлчилгээ, суурь инфляц, хүнс… → **УБ (20)** болон **улсын** тусгай индекс |
| **бүс** | Уламжлалт: Баруун / Хангай / Төв / Зүүн + УБ |
| **Шинэ бүс** | Шинэ Баруун / Хангай / Хойд / Төв / Зүүн / Говь + УБ |

Тусгай бүлгийн томьёо (elementary жигнэлт):

\[
I_g = \frac{\sum_{i \in G} w_i \cdot I_i}{\sum_{i \in G} w_i}
\]

Бүс: аймгуудын жингээр \(I_R = \sum_{a \in R} H_a I_a / \sum H_a\).

Excel гаралтын нэмэлт sheet-үүд: `Тусгай_УБ`, `Тусгай_Улс`, `Бүс_уламжлалт`, `Бүс_шинэ`.

## Дараагийн алхам

- [ ] Шинэ сарын үнэ CSV-ээс оруулах  
- [ ] 1212.mn API-тай холбох  

---
ҮСХ / үнийн статистик · суурь 2023=100
