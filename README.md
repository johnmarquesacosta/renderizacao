# Motor de Renderização de Vídeo — POC

Pipeline Python que lê um `project.json` e renderiza um vídeo dinâmico
com Ken Burns, mosaico animado, grain cinematográfico e crossfade.

---

## Instalação

```bash
pip install -r requirements.txt
```

## Uso rápido

### Opção A — gerar JSON automaticamente (recomendado para testar)

```bash
python generate_project.py images/ audio.wav project.json
python render.py project.json
```

### Opção B — usar o exemplo incluído

```bash
# edite project_example.json com seus caminhos e depois:
python render.py project_example.json
```

---

## Estrutura do project.json

```json
{
  "title":      "Título do vídeo",
  "audio":      "audio.wav",
  "fps":        30,
  "resolution": [1920, 1080],
  "output":     "output.mp4",
  "encoder":    "h264_nvenc",
  "encoder_params": ["-rc", "vbr", "-cq", "23", "-preset", "p4", "-tune", "hq"],
  "transitions": {
    "default":  "crossfade",
    "duration": 0.5
  },
  "scenes": [ ... ]
}
```

---

## Tipos de cena

### `single` — uma imagem com Ken Burns

```json
{
  "id": 1,
  "type": "single",
  "duration": 5.0,
  "images": ["images/scene_1.png"],
  "effect": "ken_burns_in",
  "overlay": ["grain", "vignette"],
  "grain_intensity": 8,
  "tilt_y": true,
  "tilt_y_degrees": 6,
  "text": {
    "content": "Transformando ideias em produto",
    "position": "bottom_center",
    "font_size": 64,
    "color": [255, 255, 255],
    "shadow": true,
    "animate": "fade_slide_up",
    "highlight": {
      "enabled": true,
      "color": [255, 220, 0],
      "alpha": 0.35,
      "padding": [4, 10]
    }
  },
  "overlay_extras": [{ "type": "particles", "count": 60, "alpha": 0.5 }],
  "transition_out": "crossfade"
}
```

### `mosaic` — múltiplas imagens surgindo lado a lado

Ideal para: "usou React, Postgres, Express, Node" → 4 ícones 9:16 compondo 16:9.
Imagens aparecem sequencialmente deslizando de baixo para cima.

```json
{
  "id": 2,
  "type": "mosaic",
  "duration": 9.0,
  "images": ["images/react.png", "images/postgres.png", "images/node.png"],
  "appear_interval": 1.8,
  "slide_duration": 0.42,
  "effect": "ken_burns_random",
  "overlay": ["grain"],
  "grain_intensity": 8,
  "grid_speed": 12,
  "overlay_extras": [
    {
      "type": "petals",
      "count": 25,
      "speed": 0.5,
      "drift": 0.4,
      "rotate": true
    }
  ],
  "bg_color": [12, 12, 12],
  "transition_out": "crossfade"
}
```

---

## Efeitos disponíveis (`effect`)

| Valor                 | Comportamento                                      |
| --------------------- | -------------------------------------------------- |
| `ken_burns_in`        | Zoom lento para dentro                             |
| `ken_burns_out`       | Zoom lento para fora                               |
| `ken_burns_pan_left`  | Desloca para a esquerda                            |
| `ken_burns_pan_right` | Desloca para a direita                             |
| `ken_burns_up`        | Desloca para cima                                  |
| `ken_burns_down`      | Desloca para baixo                                 |
| `ken_burns_drift_in`  | Zoom in + pan diagonal                             |
| `ken_burns_drift_out` | Zoom out + pan diagonal oposto                     |
| `ken_burns_random`    | Direção aleatória (determinística pelo id da cena) |

## Overlays disponíveis (lista, combináveis)

| Valor        | Efeito                         |
| ------------ | ------------------------------ |
| `grain`      | Grão cinematográfico animado   |
| `vignette`   | Escurecimento suave das bordas |
| `desaturate` | Redução parcial da saturação   |

`grain` pode ser controlado por cena com `grain_intensity` (padrão `8`) e alterna a textura a cada 2 frames para reduzir flicker.

`mosaic.grid_speed` é em pixels por segundo (padrão recomendado `12`).

`overlay_extras` suporta:

- `particles`: partículas animadas determinísticas por `scene.id`.
- `petals`: pétalas com rotação e deriva senoidal (com fallback sem PNG).

## Transições disponíveis (`transition_out`)

| Valor       | Efeito                   |
| ----------- | ------------------------ |
| `crossfade` | Fade cruzado entre cenas |

---

## Próximas extensões sugeridas

- **Tipo `reveal`** — imagem revelada da esquerda para a direita
- **Tipo `text_card`** — cartão de texto animado sobre fundo sólido
- **Efeito `parallax`** — múltiplas camadas com velocidades diferentes
- **Transição `slide_left`** — cena nova desliza por cima da anterior
- **Sync por timestamp** — cenas disparadas por marcações de tempo do áudio
- **Geração via LLM** — cada cena descrita em JSON pelo modelo

---

## Performance

| Condição         | Tempo estimado (1920×1080, 30fps) |
| ---------------- | --------------------------------- |
| Com OpenCV       | ~3–5min por 10min de vídeo        |
| Apenas PIL/numpy | ~10–15min por 10min de vídeo      |

Para testar rapidamente, reduza `resolution` para `[1280, 720]`
e use apenas 5–10 cenas no JSON antes de renderizar o projeto completo.
