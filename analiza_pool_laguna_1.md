# Analiză Proiect `jmix-cli` - Pool/Laguna #1

## Prezentare Generală

Acest proiect este un **CLI tool scris în Python** pentru generare automată de aplicații **Jmix 2.7.x** (Java 17, Spring Boot, Vaadin Flow) pe baza fișierelor CSV de configurare. CLI-ul este denumit `jmix-cli` și este disponibil ca pachet Python instalabil.

---

## Structura Proiectului

```
agilepm/
├── jmix-cli.py              # Entry point CLI
├── pyproject.toml           # Config pachet Python (setuptools)
├── build.gradle             # Config Gradle pentru aplicația Jmix
├── entities.csv             # Definiții atribute entități
├── relations.csv            # Definiții relații între entități
├── traits.csv               # Caracteristici entități (versioning, audit, soft delete)
├── roles.csv                # Roluri de securitate
├── jmix_cli/               # Modul principal Python
│   ├── __init__.py
│   ├── cli.py              # Orchestrare comenzi + dry-run
│   ├── entity.py           # Generare entități JPA
│   ├── views.py            # Generare UI (List/Detail views)
│   ├── liquibase.py        # Generare changelog-uri DB
│   ├── security.py         # Generare roluri @ResourceRole
│   ├── user.py             # Injectare relații în User built-in
│   ├── i18n.py             # Traduceri automate (Ollama)
│   └── utils.py            # Funcții utilitare + logger
└── src/main/...            # Sursa aplicației Jmix (template)
```

---

## Funcționalități CLI (`jmix-cli.py`)

### Comenzi principale:

| Comandă | Descriere |
|---------|-----------|
| `init <project> <group> [locale]` | Inițializează un nou proiect Jmix din template GitHub |
| `entity-all` | Generează TOATE entitățile + Liquibase |
| `entity <Name>` | Generează o singură entitate |
| `ui-list-all` | Generează TOATE list view-urile |
| `ui-list <Name>` | Generează list view pentru entitate |
| `ui-detail-all` | Generează TOATE detail view-urile |
| `ui-detail <Name>` | Generează detail view pentru entitate |
| `security` | Generează rolurile @ResourceRole |
| `build-all` | Generare completă (toate fazele) |
| `--dry-run` | Rulează generarea într-un director temporar (testare fără modificare) |
| `--verbose/-v` | Activează logare debug |
| `--quiet/-q` | Suprimă output-ul informativ |

---

## Fișiere CSV de Configurare

### 1. traits.csv - Caracteristici entități:
- `versioned` → adaugă `@Version` pentru optimistic locking
- `audit_of_creation` → adaugă `@CreatedBy`, `@CreatedDate`
- `audit_of_modification` → adaugă `@LastModifiedBy`, `@LastModifiedDate`
- `soft_delete` → adaugă `@DeletedBy`, `@DeletedDate`

### 2. entities.csv - Atribute entități:
- `field_name`, `field_type` (String, LocalDate, Integer, BigDecimal, etc.)
- `mandatory` (NOT NULL), `unique` (UNIQUE index)

### 3. relations.csv - Relații:
- Tipuri: `COMPOSITION_1:N`, `COMPOSITION_1:1`, `N:1`, `1:1`, `N:N`
- `ownership` pentru N:N: `owning`, `single-owning`, `both-owning`

### 4. roles.csv - Roluri de securitate:
- Generare `@ResourceRole` cu `@EntityPolicy`, `@ViewPolicy`, `@MenuPolicy`

---

## Tipuri de Relații Suportate

| Tip | Anotare JPA | UI Generat |
|-----|-------------|------------|
| **N:1** | `@ManyToOne` + `@JoinColumn` | `entityComboBox` în detail view |
| **1:1** | `@OneToOne` + `@JoinColumn` | `entityComboBox` ambele directii |
| **N:N** | `@ManyToMany` + `@JoinTable` | `multiSelectComboBoxPicker` sau `dataGrid` (după ownership) |
| **COMPOSITION_1:N** | `@Composition` + `@OneToMany` | `dataGrid` în parent, cascade delete |
| **COMPOSITION_1:1** | `@Composition` + `@OneToOne` | Camp în parent, cascade delete |

---

## Entități de Exemplu (din CSV)

```
Project (1) ←→ (N) Milestone
Milestone (1) ←→ (N) Task
Task (1) ←→ (N) TaskComment
Task → (N:1) User (assignee)
Task → (N:1) Priority (priority)
TaskComment → (N:1) User (author)
TaskComment → (N:1) Task (task)
User → (N:1) Team (team)
User ↔ (N:N) Priority (priorities)
User → (1:1) UserProfile (profile)
UserProfile → (1:1) User (user)
UserProfile → (1:1) UserConfig (profile - COMPOSITION)
Team ↔ (N:N) Client (clients - both-owning)
```

---

## Arhitectură CLI

### cli.py - Orchestrare:
- Parsing argumente CLI
- Mod `dry-run` (copie temporară + patch globals)
- Apel funcții speciale din modulele specializate
- Gestionare erori centralizată cu `JmixCliError`

### entity.py - Generare entități:
- Citire din CSV → `gen_entity_mechanic_from_csv()`
- Build imports, fields, getteri/setteri
- Injectare relații (N:1, 1:1, N:N)
- `get_sorted_entities_by_dependency()` - sortare topologicală pentru generare corectă

### views.py - Generare UI:
- `gen_list_view_from_csv()` - `StandardListView` + DataGrid
- `gen_detail_view_from_csv()` - `StandardDetailView` + formLayout
- Injectare UI pentru relații composition în parent
- Injectare UI specială pentru User built-in (Jmix)

### liquibase.py - Migrate DB:
- `gen_liquibase_changelog_from_csv()` - tabel + coloane + indexuri
- `gen_liquibase_relations_changelog()` - FK + junction tables

### security.py - RBAC:
- `gen_jmix_resource_roles_from_csv()` - roluri `@ResourceRole`

### i18n.py - Internaționalizare:
- `ask_ollama_translation()` - traducere automată via Ollama API
- `update_messages_entity()` - generare `messages_*.properties`

### user.py - Extindere User:
- Injectare câmpuri relații în clasa `User` built-in Jmix
- Generare relații inverse automat

---

## Testare & CI

- Teste JUnit în `src/test/java/`
- `./gradlew test` - rulează testele
- Template-ul include `AgileDemoDataInitializer` pentru demo data

---

## Instalare & Rulare

```bash
# Instalare pentru dezvoltare
pip install -e .

# Sau rulare directă
python3 jmix-cli.py --help

# Generare completă
python3 jmix-cli.py build-all

# Testare cu dry-run
python3 jmix-cli.py --dry-run build-all
```

---

## Caracteristici Unice

1. **Dry-Run Mode** - generează fără a modifica proiectul curent
2. **Traduceri automatice** - integrare cu Ollama (model `translategemma:4b`)
3. **Audit addon auto-config** - adaugă dependințele dacă `audit_of_creation/modification=true`
4. **Relații complexe** - suport pentru COMPOSITION, N:N cu ownership, relații inverse
5. **User built-in extend** - poate adăuga relații direct în `User.java` al lui Jmix
6. **Gestion are erori centralizată** - ierarhie `JmixCliError` → `ConfigurationError`, `GenerationError`, `UserInputError`, `InvalidCsvError`

---

## Concluzie

`jmix-cli` este un **instrument puternic de scaffolding** pentru aplicații Jmix care:
- **Elimină boilerplate-ul** manual al entităților, view-uri, securitate
- **Centralizează configurarea** în fișiere CSV simple
- **Suportă relații complexe** JPA (Composition, ManyToMany, bidirectional)
- **Are integrare i18n** automată
- **Este extensibil** și ușor de înțeles (modular, fără dependințe externe)

---

*Analiză generată automat - 2026-07-28*