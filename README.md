# Halloween do New Life 🎃

Webcam com detecção de movimento e uma sequência de sustos. O modo atual toca **barulhos assustadores e “Bem-vindos ao Halloween do New Life!”**, com gritos sem palavras, morcegos, gargalhadas, vento, madeira e motosserra.

## Rodar o projeto

Na pasta do projeto, execute:

```sh
conda activate halloween
python main.py
```

No macOS, também é possível dar dois cliques em **iniciar.command**. O iniciador usa o ambiente Conda `halloween`.

A Redragon está configurada como câmera `0`, usando `avfoundation`. Se o macOS pedir, permita o acesso à câmera para o aplicativo que executa o programa em **Ajustes do Sistema → Privacidade e Segurança → Câmera**. Feche e reabra esse aplicativo se a permissão não for reconhecida.

## Como funciona

1. Ao abrir a câmera, o programa aprende a cena durante `WARMUP_SECONDS`. Mantenha a webcam fixa nesse período.
2. O áudio começa somente depois de **mais de 3 segundos de movimento contínuo**. Se o movimento parar antes disso, a contagem zera.
3. A sequência toca um grito inicial, os morcegos, a saudação do New Life, a gargalhada, uma pausa na sequência principal, outro susto e o ambiente final. O fundo de efeitos continua durante a pausa.
4. Após **5 segundos sem movimento**, todos os sons são interrompidos. Para recomeçar, é necessário confirmar movimento contínuo novamente.
5. Se o ciclo chegar ao fim e o movimento tiver continuado, pode recomeçar imediatamente, sem uma nova espera entre ciclos.

A prévia abre **em janela, no tamanho original da imagem da câmera**, em cores e com orientação real. A detecção usa uma imagem reduzida para economizar processamento. O programa mantém os quadros em memória e não grava fotos nem vídeos.

## Configurar

Edite **.env** e reinicie o programa para aplicar. **.env.example** é um modelo para outras instalações; ele usa seleção automática da câmera e 30 segundos de ambiente, enquanto o `.env` deste computador usa a Redragon e a duração ajustada localmente.

Os dois arquivos têm seções e comentários para todas as opções. Variáveis definidas no terminal têm prioridade sobre o arquivo.

| Opção | O que controla |
| --- | --- |
| `AUDIO_MODE=sons_e_boas_vindas` | Barulhos e a saudação, com as demais mensagens desativadas. |
| `START_MOTION_SECONDS=3` | Exige mais de 3 segundos contínuos para iniciar. `0` usa apenas a confirmação por quadros. |
| `STOP_IF_NO_MOTION_SECONDS=5` | Interrompe tudo após 5 segundos sem movimento. `0` desativa a interrupção. |
| `REARM_QUIET_SECONDS=0` | Permite repetir sem exigir cena parada entre ciclos. |
| `COOLDOWN_SECONDS=0` | Permite repetir sem intervalo adicional depois que o ciclo termina. |
| `SCARE_DELAY_SECONDS` | Pausa da sequência principal entre a gargalhada e o segundo susto. |
| `AMBIENCE_SECONDS` | Duração do ambiente depois do segundo susto. |
| `MASTER_VOLUME` | Volume geral de todos os sons, de `0` a `1`. |
| `INTRO_VOLUME`, `SCARE_VOLUME`, `AMBIENCE_VOLUME` | Volume de cada etapa. |
| `BACKGROUND_SCREAMS_VOLUME` | Volume independente dos gritos sem palavras e da motosserra ao fundo no modo atual. |
| `PREVIEW_FULLSCREEN=false` | Abre em janela. Use `true` para abrir em tela cheia. |
| `MIRROR_PREVIEW=false` | Mantém a orientação real da cena. |

A duração atual do ambiente é **15 segundos**. A pausa antes do segundo susto é de **3 segundos**. Consulte o `.env` para os valores mais recentes.

### Modos de áudio

- **`sons_e_boas_vindas`**: modo ativo, com uma única frase e efeitos. Usa `audio/05_fundo_sons.wav` como fundo.
- **`completo`**: modo alternativo preservado, com mensagens de socorro e ameaças. Usa `audio/04_gritos_fundo.wav`.

Troque `AUDIO_MODE` e reinicie para mudar o fundo usado ao vivo. O arquivo `audio/halloween_exemplo.wav` representa o modo e os valores da última montagem; execute `python gerar_audio.py` para atualizá-lo após uma mudança.

## Calibrar o movimento

```sh
python main.py --calibrar
```

Esse modo mostra a imagem real, os indicadores e um painel com a máscara de movimento **sem tocar áudio**. Branco na máscara indica áreas que mudaram.

| Situação | Ajuste |
| --- | --- |
| Não detecta movimentos pequenos | Diminua `MIN_CONTOUR_AREA`, `DIFFERENCE_THRESHOLD` ou `MIN_MOTION_RATIO`. |
| Dispara com pequenos ruídos | Aumente os mesmos limites ou `CONSECUTIVE_FRAMES`. |
| Cortina, ventilador ou rua interferem | Restrinja a região monitorada com `ROI_X`, `ROI_Y`, `ROI_WIDTH` e `ROI_HEIGHT`. |
| Uma pessoa próxima é ignorada | Aumente `MAX_MOTION_RATIO`; `1` desativa o filtro de mudança global de luz. |
| Detecção consome muito processamento | Diminua `PROCESSING_WIDTH` ou `PROCESSING_FPS`; recalibre a área mínima ao mudar a largura. |

A área mínima usa pixels da imagem de processamento. As opções ROI usam frações de `0` a `1` da imagem original: `X + WIDTH` e `Y + HEIGHT` devem ser menores ou iguais a `1`.

`BACKGROUND_ALPHA` define quanto o fundo se adapta. Pessoas que ficam completamente paradas podem passar a fazer parte da referência: o programa detecta mudanças na imagem, não reconhece pessoas. O filtro de iluminação também depende da calibração do ambiente.

## Ouvir sem câmera

```sh
python main.py --testar-audio
```

Reproduz um ciclo sem abrir a webcam e sem aplicar a parada por falta de movimento. Também é possível abrir **audio/halloween_exemplo.wav** em um reprodutor.

## Remontar o áudio

No modo atual, o gerador reutiliza a saudação pronta indicada por `SOURCE_GREETING_VOICE` e as fontes de efeitos já incluídas. Não precisa de internet, Runway ou ferramenta de geração de voz para montar ou reproduzir essa versão.

```sh
python gerar_audio.py
```

Execute após mudar parâmetros de geração, como `VOICE_GAIN`, `WITCH_GAIN`, `CHAINSAW_GAIN`, `OPENING_SCREAM_GAIN`, `SCARE_SOUND_SECONDS` ou a distribuição dos efeitos. Alterações apenas nos volumes de reprodução e nos tempos de execução exigem reiniciar o programa; remonte também o exemplo se quiser ouvir esses novos valores no arquivo completo.

Para usar outra gravação de boas-vindas:

```sh
python gerar_audio.py --voz-arquivo /caminho/boas_vindas.wav
```

Use WAV PCM de 16 bits. Para tornar a troca permanente, altere `SOURCE_GREETING_VOICE` no `.env`. Mudar somente `SPEECH_TEXT` não grava uma nova frase no modo atual: o texto precisa corresponder à gravação fornecida.

O modo completo mantém as falas locais antigas em cache. `--reutilizar-voz` reutiliza a saudação antiga desse modo. Regenerar falas do modo completo com outros textos ou vozes utiliza o sintetizador local: `say` e FFmpeg no macOS, ou `espeak-ng` no Linux. Isso não é necessário para rodar ou remontar **sons e boas-vindas**.

## Arquivos mantidos

| Caminho | Uso |
| --- | --- |
| `main.py` | Inicia a câmera, a detecção, a prévia e o áudio. |
| `halloween/` | Configuração, detector, prévia e controle da sequência. |
| `gerar_audio.py` | Monta os WAV a partir das fontes existentes. |
| `iniciar.command` | Iniciador para macOS usando Conda. |
| `audio/01_boas_vindas.wav` | Abertura montada com a saudação. |
| `audio/02_susto.wav` | Segundo susto. |
| `audio/03_ambiente.wav` | Ambiente final em loop. |
| `audio/04_gritos_fundo.wav` | Fundo do modo completo. |
| `audio/05_fundo_sons.wav` | Fundo do modo sons e boas-vindas. |
| `audio/halloween_exemplo.wav` e `.json` | Montagem completa e horários das etapas. |
| `audio/falas_ia/boas_vindas.wav` e `.json` | Saudação de IA aprovada e registro de origem. |
| `audio/fontes/` | Fontes necessárias para remontar os efeitos e falas locais do modo completo. |
| `audio/voz_original.wav` e `.json` | Saudação local antiga, para a remontagem do modo completo. |
| `audio/FONTES.md` | Autores, origem e licenças dos sons. |
| `tests/` | Testes sem webcam nem saída de som. |

Duplicatas de download, tentativas de voz descartadas, o gerador experimental de falas e o ambiente `.venv` antigo foram removidos. O projeto usa o ambiente Conda `halloween`.

## Controles

| Tecla | Ação |
| --- | --- |
| **Q** | Encerra o programa. |
| **F** | Alterna tela cheia e janela. |
| **Esc** | Sai da tela cheia; em janela, encerra. |
| **S** | Interrompe manualmente o áudio e exige pelo menos 2 segundos de repouso antes de rearmar. |
| **R** | Recalibra o fundo; mantenha a cena parada durante o aquecimento. |
| **Ctrl+C** | Encerra pelo terminal. |

## Instalar em outro computador

Com o Conda disponível, execute na pasta do projeto:

```sh
conda env create -f environment.yml
conda activate halloween
python main.py
```

Em outro sistema ou com outra webcam, ajuste `CAMERA_BACKEND` e `CAMERA_INDEX`. Os WAV já estão incluídos. Para a prévia, use `opencv-python`, e não `opencv-python-headless`.

## Verificar e resolver problemas

```sh
# Validar configuração e arquivos, sem câmera nem som:
python main.py --verificar

# Rodar sem janela; encerre com Ctrl+C:
python main.py --sem-janela

# Usar outra configuração:
python main.py --env configuracao_festa.env

# Executar os testes:
python -m unittest discover -s tests -v
```

Se a câmera não abrir, feche outros aplicativos que a utilizem e confira a permissão do sistema. Para a Redragon deste Mac, mantenha `CAMERA_INDEX=0` e `CAMERA_BACKEND=avfoundation`. Se o som falhar, deixe `AUDIO_DEVICE` vazio e confira a saída padrão do sistema. Use `LOG_LEVEL=DEBUG` para ver detalhes de erros.

Todos os caminhos relativos de áudio são resolvidos a partir da pasta deste projeto, inclusive com `--env`.

## Referências

- [Créditos e licenças dos áudios](audio/FONTES.md)
- [OpenCV: detecção de mudanças contra o fundo](https://docs.opencv.org/4.x/d1/dc5/tutorial_background_subtraction.html)
- [Pygame: reprodução de áudio](https://www.pygame.org/docs/ref/music.html)
- [python-dotenv: configuração por arquivo](https://bbc2.github.io/python-dotenv/)
