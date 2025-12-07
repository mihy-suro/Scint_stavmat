# Parametry pro NaI(Tl) detektor

Přidej tento sheet "Parametry" do svého NaI(Tl) Excel souboru:

| Parametr       | Hodnota          | Poznámka |
|----------------|------------------|----------|
| Ra_faktor      | 13.9             | Konverzní faktor Ra-226 (TODO: ověřit pro NaI) |
| K_faktor       | 212              | Konverzní faktor K-40 (TODO: ověřit pro NaI) |
| Th_faktor      | 7.4              | Konverzní faktor Th-232 (TODO: ověřit pro NaI) |
| ref_a0         | ??.????          | Referenční kalibrace a₀ (intercept) |
| ref_a1         | ?.????           | Referenční kalibrace a₁ (slope) |
| ref_a2         | 0                | Referenční kalibrace a₂ (kvadratický člen) |
| manual_a0      | ??.????          | Manuální kalibrace a₀ |
| manual_a1      | ?.????           | Manuální kalibrace a₁ |
| skip_rows      | 11               | Počet řádků k přeskočení při načítání dat |
| cut_channel    | 150              | Kanál, pod kterým se vynulují data (šum) |

## Jak zjistit hodnoty pro NaI(Tl)?

### 1. Referenční kalibrace (ref_a0, ref_a1)
- Použij známé zdroje (Cs-137 662 keV, Co-60 1173/1332 keV)
- Změř polohu píků v kanálech
- Vypočítej: E = a₀ + a₁ × CH
- Např: Cs-137 pík v kanálu 135 → a₁ = 662/135 ≈ 4.9 keV/kanál

### 2. Konverzní faktory (Ra_faktor, K_faktor, Th_faktor)
- Závislé na geometrii, objemu vzorku, účinnosti detektoru
- Kalibrace pomocí referenčních vzorků se známou aktivitou
- Nebo přepočti z CeBr hodnot pomocí poměru účinností

### 3. Cut channel
- Podívej se na nízkoenergetickou část spektra
- Nastav tam, kde začíná smysluplný signál (typicky 50-200 pro NaI)

## Příklad pro typický 3"×3" NaI(Tl):
```
ref_a0 ≈ 0-50 keV (malý offset)
ref_a1 ≈ 3-6 keV/kanál (záleží na zesilovači)
```

Máš nějaké kalibrační měření pro NaI(Tl)?
