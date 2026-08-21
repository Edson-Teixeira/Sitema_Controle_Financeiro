# App_IA - Aplicação de Gestão Financeira

Aplicação Django com REST Framework e interface Single Page Application (SPA).

---

## ⚡ Compatibilidade com Linux Umbrel OS

**Sim, este projeto é 100% compatível com o Linux Umbrel OS.**

O Umbrel OS é um sistema operacional Linux para servidores pessoais (Raspberry Pi e x86_64) que executa aplicações em containers Docker.

### Como Executar no Umbrel OS

#### Opção A: Execução via SSH (Docker Compose Direct)
1. Acesse o seu servidor Umbrel via SSH:
   ```bash
   ssh umbrel@umbrel.local
   ```
2. Clone ou envie a pasta deste projeto para o servidor.
3. Acesse a pasta do projeto e inicie os containers:
   ```bash
   cd App_IA
   docker compose up -d --build
   ```
4. A aplicação estará disponível no IP do seu Umbrel na porta `8000` (ex: `http://umbrel.local:8000`).

#### Opção B: Instalação como Custom App no Dashboard do Umbrel
O projeto inclui o manifesto `umbrel-app.yml` pré-configurado. Basta adicionar esta pasta no repositório de aplicativos locais do seu Umbrel (`~/umbrel/apps/` ou App Store customizada) para visualizá-lo e instalá-lo diretamente no painel web do Umbrel.

---

## 🚀 Como Executar com Docker (Geral)

### Pré-requisitos
- [Docker](https://www.docker.com/) instalado.
- [Docker Compose](https://docs.docker.com/compose/) instalado.

### Passo a Passo

1. **Construir e Iniciar os Containers**:
   ```bash
   docker compose up --build
   ```

2. **Acessar a Aplicação**:
   Abra o navegador e acesse [http://localhost:8000](http://localhost:8000).

3. **Parar a Aplicação**:
   ```bash
   docker compose down
   ```

---

## 🐍 Como Executar Localmente (Sem Docker)

### Pré-requisitos
- Python 3.11 ou superior.

### Passo a Passo

1. **Criar e Ativar Ambiente Virtual**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Instalar Dependências**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Executar Migrações do Banco de Dados**:
   ```bash
   python manage.py migrate
   ```

4. **Popular Dados Iniciais (Opcional)**:
   ```bash
   python manage.py seed_data
   ```

5. **Iniciar o Servidor de Desenvolvimento**:
   ```bash
   python manage.py runserver
   ```

   Acesse [http://127.0.0.1:8000](http://127.0.0.1:8000).
