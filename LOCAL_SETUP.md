# Ambiente local DDpai

As entradas locais estao em `working_data/` e sao ignoradas pelo Git. Nesta
maquina, elas apontam para o cartao montado em `/run/media/fabiano/disk/DCIM`:

- `working_data/photos/{front,rear,tmp}`: fotos da camera;
- `working_data/tar`: arquivos GPS;
- `working_data/videos/{front,rear}`: videos da camera.

Com o cartao conectado, extraia as fotos para uma copia local com:

```bash
./tools/extract_photos.sh
```

O destino padrao e `extracted_photos/`, tambem ignorado pelo Git. O comando
preserva metadados, nunca modifica o cartao e nao sobrescreve uma exportacao
anterior. Para apenas conferir o que sera copiado:

```bash
./tools/extract_photos.sh working_data/photos extracted_photos --dry-run
```

As imagens em `tmp` sao temporarias; inclua-as somente se necessario:

```bash
./tools/extract_photos.sh working_data/photos extracted_photos --include-tmp
```

Para construir o painel GPS/videos, os defaults agora usam as pastas locais:

```bash
./build.sh
```
