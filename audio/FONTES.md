# Fontes do áudio de bruxas

No modo **sons_e_boas_vindas**, a única frase usada é a saudação em `falas_ia/boas_vindas.wav`, gerada com o modelo público [Chatterbox em português brasileiro](https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br). Sua origem e parâmetros estão em `falas_ia/boas_vindas.json`. As falas locais de socorro e de ameaça descritas abaixo pertencem ao modo completo e não são usadas no modo só sons. O fundo sem falas está em `05_fundo_sons.wav`.

Esta versão usa uma interpretação gravada de gargalhada e grito, asas e guinchos de morcegos, vento e foley de madeira. As fontes abaixo estão sob [Creative Commons Zero (CC0)](https://creativecommons.org/publicdomain/zero/1.0/). Os links apontam para as páginas dos autores e suas declarações de licença.

| Arquivo usado | Autor e fonte | Tratamento |
| --- | --- | --- |
| `fontes/risada_bruxa.wav` | AuraVoice / Nocturnal_Vanguard — [Evil Cackle Laugh 1](https://opengameart.org/content/evil-cackle-laugh-1) | Gargalhada interpretada, com pequenas variações de velocidade e reverberação de sala. |
| `fontes/grito_bruxa.wav` | AuraVoice / Nocturnal_Vanguard — [Female Scream 1](https://opengameart.org/content/female-scream-1) | Grito interpretado, com reverberação curta; usado no susto. |
| `fontes/morcego.wav` | AntumDeluge, a partir de gravação de polymorpheva — [Bat Screeches](https://opengameart.org/content/bat-screeches) | `bat_01.flac` convertido para WAV. |
| `fontes/asas.wav` | AntumDeluge, a partir de som de dave.des — [Large Wings Flap](https://opengameart.org/content/large-wings-flap) | Foley de asas, acelerado levemente para a passagem de morcegos. |
| `fontes/vento.wav` | remaxim — [Short wind sound](https://opengameart.org/content/short-wind-sound) | Rajadas sobrepostas, com suavização e variação de intensidade. |
| `fontes/porta_batendo.wav` | rubberduck — [100 CC0 metal and wood SFX](https://opengameart.org/content/100-cc0-metal-and-wood-sfx) | Apenas `wood_slam_02.ogg`, uma batida de madeira; nenhum efeito metálico do pacote é usado. |
| `fontes/madeira_rangendo.wav` | rubberduck — [100 CC0 metal and wood SFX](https://opengameart.org/content/100-cc0-metal-and-wood-sfx) | Apenas `wood_squeak_01.ogg`, para o ambiente de casa assombrada. |
| `fontes/motosserra.wav` | Joseph SARDIN — [Chain saw](https://bigsoundbank.com/chain-saw-s0454.html) | Gravação de motosserra em uso, publicada sob CC0. Fragmentos com entrada e saída suaves na camada baixa de fundo. |

As fontes utilizadas estão em WAV PCM 16 bits, mono, 44.100 Hz. Os pacotes ZIP e os arquivos de download duplicados foram removidos; as páginas de origem e licenças permanecem registradas acima.

A saudação do modo atual usa o arquivo de IA descrito no início deste documento. Os arquivos `voz_original.wav` e `fontes/fala_fundo_*.wav` são gravações locais antigas preservadas para a remontagem do modo completo: a saudação e as ameaças usam Grandma, e os pedidos de socorro usam Eddy, ambas vozes do macOS em português brasileiro. Essas falas não tocam no modo `sons_e_boas_vindas`. A gargalhada e o grito sem palavras são interpretações humanas gravadas pela artista indicada acima.

O gerador mistura essas fontes em estéreo, preservando a respiração e o ritmo irregular das vozes. A pausa da sequência principal após a gargalhada continua com 3 segundos; a camada baixa de fundo segue tocando durante essa pausa. O ambiente final respeita `AMBIENCE_SECONDS` no `.env`. A montagem completa está em `halloween_exemplo.wav`.
