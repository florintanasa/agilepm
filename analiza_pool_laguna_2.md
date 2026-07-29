# Analiză a proiectului `agilepm` — scriptul `jmix-cli.py` și submodulele

## 1. Prezentare generală

Acest proiect este o **aplicație full-stack Jmix 2.7.x** (Java 17 + Spring Boot + Vaadin Flow) pentru managementul proiectelor agile. Pe lângă aplicația Java, conține un **instrument CLI în Python** (`jmix-cli.py`) care generează scaffold-ul aplicației (entități, view-uri, changelogs Liquibase, mesaje i18n, roluri de securitate) din **fișiere CSV** care servesc ca schemă declarativă a domeniului.

### Structura de fișiere cheie

| Fișier / Director | Scop |
|---|---|
| `jmix-cli.py` | Punct de intrare — wrapper minimal |
| `jmix_cli/` | Pachetul Python cu toate modulele de generare |
| `pyproject.toml` | Configurația pachetului (setuptools, entry point `jmix-cli`) |
| `entities.csv` | Definirea câmpurilor entităților |
| `relations.csv` | Definirea relațiilor între entități |
| `traits.csv` | Trăsături arhitecturale (versionare, audit, soft-delete) |
| `roles.csv` | Roluri de securitate RBAC |
| `build.gradle`, `settings.gradle` | Configurația proiectului Gradle |
| `src/main/java/.../entity/` | Entitățile Java generate |
| `src/main/resources/.../liquibase/` | Changelog-urile Liquibase generate |
| `src/main/resources/.../view/` | View-urile XML generate |
| `AGENTS.md` | Reguli de dezvoltare pentru agenți AI |

---

## 2. `jmix-cli.py` — punctul de intrare

```python
#!/usr/bin/env python3
# ... BSD-2-Clause license header ...
from jmix_cli.cli import main

if __name__ == "__main__":
    main()
```

Este un **wrapper de 31 de linii** — toată logica e în pachetul `jmix_cli`. Folosește licența BSD-2-Clause. Poate fi rulat direct (`python3 jmix-cli.py ...`) sau ca comandă instalată (`jmix-cli ...`) datorită entry point-ului din `pyproject.toml`:

```toml
[project.scripts]
jmix-cli = "jmix_cli.cli:main"
```

---

## 3. `pyproject.toml` — ambalajare

- **Build backend:** `setuptools`
- **Python:** >= 3.10 (folosește `list[str]` syntax, `|` pentru union types)
- **Dependențe:** doar biblioteci standard (`csv`, `json`, `http.client`, `pathlib`, etc.) — fără dependențe externe
- **Entry point:** `jmix-cli = "jmix_cli.cli:main"`

---

## 4. Modulele pachetului `jmix_cli`

### 4.1 `__init__.py` (25 linii)
Conține doar antetul de licență. Nu exportă nimic.

### 4.2 `exceptions.py` (47 linii) — Ierarhia de excepții

O ierarhie de excepții centralizate, înlocuind `sys.exit()`-urile distribuite:

```
JmixCliError (bază)
├── ConfigurationError       — fișiere config/project invalide
│   └── InvalidCsvError      — CSV lipsă sau schema invalidă (cu file_path, missing_columns)
│   └── MissingProjectError  — nu e un proiect Jmix valid
├── GenerationError          — eșec la generarea de cod
│   └── GitOperationError    — eșec la operațiuni git
└── UserInputError           — argumente CLI invalide
```

`InvalidCsvError` este utilă — capturează `file_path` și `missing_columns` pentru mesaje de eroare clare.

### 4.3 `utils.py` (133 linii) — Funcții utilitare

Conține:
- **`get_logger(name)`** — logger cu format `[LEVEL] message` către stdout
- **`get_project_name()` / `get_company_name()`** — parsează `settings.gradle` și `build.gradle` pentru a extrage `rootProject.name` și `group`
- **Variabile globale modulare:** `PROIECT_PATH`, `PROJECT`, `project_name`, `COMPANY`, `company_path` — calculate la importare din fișierele de configurare. Acestea sunt **patch-uite** în mod temporal pentru dry-run (vezi `_patch_globals_for_dry_run` în `cli.py`)
- **`to_camel_case_lower()`** — face primul caracter lowercase
- **`inject_import_if_missing()`** — adaugă un import în fișierul Java dacă nu există deja, inserându-l după declarația `package`
- **`validate_csv_path()`** — validează existența CSV-ului și verifică coloanele necesare
- **`ensure_dir()` / `write_file()`** — utilitare pentru scriere fișiere
- **`append_unique()`** — adaugă linii într-un fișier `.properties` fără dubluri, cu antet de comentariu

### 4.4 `cli.py` (914 linii) — Orchestratorul principal

Acesta este cel mai mare și complex modul. Conține:

#### Funcții de bază:
- **`_read_project_name()` / `_read_company_name()`** — duplicate ale funcțiilor din `utils.py`, dar care primesc un `Path` ca parametru (pentru dry-run)
- **`_ensure_dry_run_server_port()`** — setează `server.port=0` în `application.properties` pentru dry-run
- **`_copy_project_to_temp()`** — copiază proiectul curent într-un director temporar, păstrând doar fișierele necesare (`gradle/`, `build.gradle`, `settings.gradle`, `gradle.properties`, `gradlew`, `gradlew.bat`, CSV-urile, și `src/`). **Curăță changelogs-urile Liquibase** din directorul temporar (păstrând doar `010-init-user.xml`), astfel încât să nu fie duplicate la re-generare.
- **`_patch_globals_for_dry_run()`** — **cheia dry-run-ului**: actualizează variabilele globale (`PROIECT_PATH`, `PROJECT`, `project_name`, `COMPANY`, `company_path`) în toate modulele (`utils`, `entity`, `views`, `liquibase`, `security`, `user`, `i18n`) și în `globals()` curente, astfel încât toate modulele să scrie în directorul temporar în loc de cel original.
- **`_print_dry_run_summary()`** — afișează statistici (număr fișiere Java/XML/properties generate) și comenzi sugerate (`meld`, `cd ... && ./gradlew bootRun`)
- **`_finish_dry_run()`** — wrapper pentru sumar
- **`_handle_error()`** — handler centralizat pentru erori: loghează cu prefixul potrivit și apelează `sys.exit(1)`

#### Comenzi CLI:
| Comandă | Scop |
|---|---|
| `init <name> <group> [locale]` | Clonează un template Git (`jmix-ai-template` branch `v2.8.2`), refactorează pachetele, adaugă dependența de traduceri |
| `entity-all` | Generează toate entitățile + changelogs + mesaje + compuneri |
| `entity <Name>` | Generează o singură entitate (cu suport pentru actualizare incrementală) |
| `ui-list-all` / `ui-list <Name>` | Generează view-urile de tip listă |
| `ui-detail-all` / `ui-detail <Name>` | Generează view-urile de tip detaliu |
| `security` | Generează rolurile de securitate |
| `build-all` | **Secvența completă** în 3 faze (entități → view-uri → securitate) |
| `migrate <Name>` / `migrate-all` | Migrații incrementale de baze de date |
| `help` / `--help` / `-h` | Afișează ajutorul |

#### Faze din `build-all`:
1. **FAZĂ 1** — Modelare date + changelogs: generează entitățile Java, changelogs-urile Liquibase (baze + relații + FK), mesajele i18n. Tratează separat entitatea `User` (sistemului).
2. **FAZĂ 1.6** — Compuneri: injectează relațiile `COMPOSITION_1:N` în entitățile părinte și generează changelogs-urile FK.
3. **FAZĂ 1.7** — Relații în User: injectează relațiile în entitatea `User` existentă.
4. **FAZĂ 2** — View-uri FlowUI: generează view-urile listă și detaliu pentru fiecare entitate, actualizează `menu.xml`, injectează UI pentru relațiile N:N.
5. **FAZĂ 3** — Securitate: generează rolurile de acces.

#### Funcție cheie: `_generate_single_entity(name)`
Gestionează generarea unei singure entități cu logică de **actualizare incrementală**:
- Verifică dacă entitatea există deja (`has_existing_entity_and_changelog`)
- Dacă există: actualizează fișierul Java și rulează `migrate_entity` în mod "quiet" pentru a detecta noi coloane
- Dacă este nouă: generează tot (entitate + changelog + mesaje)

#### Funcție cheie: `_finalize_composition_relationships()`
Parcurge `relations.csv` pentru relațiile de tip `COMPOSITION_1:1` și:
- Injectează câmpurile `@Composition` în ambe entități (sursă și invers)
- Generează un changelog FK dedicat pentru fiecare compunere 1:1

#### Funcție cheie: `_update_menu(n)`
Adaugă o intrare în `menu.xml` pentru fiecare entitate generată, folosind cheia `msg://` pentru titlu.

#### Funcție cheie: `inject_audit_dependencies()`
Verifică `traits.csv` pentru audit și:
- Adaugă dependențele `jmix-audit-starter` și `jmix-audit-flowui-starter` în `build.gradle`
- Adaugă `<include file="/io/jmix/audit/liquibase/changelog.xml"/>` în `changelog.xml`

#### Funcție cheie: `cmd_init_project()`
Clonează template-ul `jmix-ai-template` (branch `v2.8.2`), refactorează pachetele Java (`io.jmix.tempate` → pachetul specificat), adaugă dependența de traduceri, creează fișierele de mesaje pentru limba cerută, și inițializează un repo Git.

### 4.5 `entity.py` (555 linii) — Generarea entităților

#### Funcții de citire CSV:
- **`get_traits_from_csv()`** — citește trăsăturile (versioned, audit_of_creation, audit_of_modification, soft_delete) pentru o entitate
- **`get_entities_from_csv()`** — citește câmpurile business (name, type, mandatory, unique) pentru o entitate
- **`get_relations_from_csv()`** — citește relațiile (type, target, field, mandatory, ownership) pentru o entitate
- **`get_sorted_entities_by_dependency()`** — **topological sort** a entităților bazat pe relațiile N:1, 1:1, 1:N. Folosește DFS cu detectare de cicluri (prin `visiting` set). Adaugă `User` la final dacă nu este în CSV.

#### Funcții de generare:
- **`_build_imports_and_fields()`** — generează câmpurile și metodele pentru trăsături (versionare, audit, soft-delete), câmpurile business și importurile necesare
- **`_build_relation_fields_and_methods()`** — generează câmpurile pentru toate tipurile de relații:
  - **N:1**: `@ManyToOne` + `@JoinColumn`
  - **1:N**: `@OneToMany(mappedBy=...)`
  - **1:1**: `@OneToOne` + `@JoinColumn` + injectare inversă în entitatea țintă
  - **N:N**: `@ManyToMany` + `@JoinTable` + injectare inversă (owning/both-owning/mappedBy)
  - **COMPOSITION_1:N**: `@Composition` + `@OneToMany(mappedBy=...)`
  - **COMPOSITION_1:1**: `@Composition` + `@OneToOne` + `@JoinColumn`
- **`_inject_composition_into_parent()`** — injectează relațiile de compunere în entitatea părinte (inverse side)
- **`gen_entity_mechanic_from_csv()`** — funcția principală: generează clasa Java completă a entității, cu:
  - `@JmixEntity`, `@Table` (cu indexuri unique dacă e cazul)
  - `@Id` + `@JmixGeneratedValue` + UUID
  - Câmpurile de trăsătură, business și relație
  - Metodele getter/setter
  - `@InstanceName` pe primul câmp String
- **`has_existing_entity_and_changelog()`** — verifică dacă o entitate există deja (fișier Java + changelog) pentru suportul de actualizare incrementală

### 4.6 `liquibase.py` (264 linii) — Generarea changelogs-urilor

- **`map_type()`** — maphează tipurile Java la tipurile SQL (String→VARCHAR(255), BigDecimal→NUMERIC(19,2), etc.)
- **`_stable_changeset_id()`** — generează ID-uri stabile pentru changesets (ex: `project-base`, `project-add-fk-field`)
- **`gen_liquibase_changelog_from_csv()`** — generează changelog-ul de bază pentru o entitate: `createTable` cu coloanele ID, VERSION, audit, și coloanele business. Adaugă și indexuri unice ca changesets separate.
- **`gen_liquibase_relations_changelog()`** — generează changelogs pentru relații:
  - **N:1**: `addColumn` + `addForeignKeyConstraint`
  - **1:1 / COMPOSITION_1:1**: `addColumn` + `createIndex` (unique) + opțional `addForeignKeyConstraint`
  - **N:N**: `createTable` pentru tabelul de legătură + chei primare + FKi

### 4.7 `views.py` (736 linii) — Generarea view-urilor FlowUI

- **`gen_list_view_from_csv()`** — generează XML-ul și Java-ul pentru un list view:
  - `collection` DataProvider cu fetch plan
  - `dataGrid` cu coloane pentru toate proprietățile
  - `genericFilter`, `pagination`, `actions`
  - `StandardListView` extins
- **`gen_detail_view_from_csv()`** — generează XML-ul și Java-ul pentru un detail view:
  - `instance` DataProvider
  - `formLayout` cu componente potrivite pentru fiecare tip de câmp (textField, checkBox, datePicker, entityComboBox, multiSelectComboBoxPicker)
  - `StandardDetailView` extins
  - Apelează `_inject_composition_ui_into_parent()` pentru a adăuga UI-ul compunerii
- **`_inject_composition_ui_into_parent()`** — injectează un `dataGrid` pentru colecțiile de compunere în view-ul detaliu al entității părinte
- **`inject_list_ui_into_existing_user()`** / **`inject_detail_ui_into_existing_user()`** — adaugă coloanele și componentele pentru relațiile N:1, 1:1, N:N în view-urile existente ale lui `User`
- **`inject_nn_grid_into_inverse_entity()`** — pentru relațiile N:N, adaugă un `dataGrid` în view-ul entității inverse (depinzând de `ownership`)
- **`inject_nn_datagrid_into_source_entity()`** — pentru `both-owning`, înlocuțește `multiSelectComboBoxPicker`-ul cu un `dataGrid` cu acțiuni de add/exclude
- **`_infer_inverse_n_n_field()`** — inferă numele câmpului invers pentru N:N printr-o expresie regulată pe fișierul Java
- **`_get_property_columns()`** — obține coloanele de afișat pentru o colecție (folosește primul câmp String, sau `username` pentru User)

### 4.8 `security.py` (133 linii) — Generarea rolurilor

- **`gen_jmix_resource_roles_from_csv()`** — citește `roles.csv` și generează interfețe `@ResourceRole` Java:
  - Grupează politicile după `code` (fiecare cod = un rol)
  - Pentru fiecare entitate din rol: generează `@ViewPolicy`, `@MenuPolicy`, `@EntityPolicy` (CRUD), `@EntityAttributePolicy`
  - Numele clasei este derivat din cod (ex: `project-manager` → `ProjectManagerRole`)
  - Folosește `EntityAttributePolicyAction.MODIFY` când există permisiuni de create/update, altfel `VIEW`

### 4.9 `user.py` (211 linii) — Injectarea relațiilor în User

Deoarece `User` este o entitate existentă a Jmix (nu generată de CLI), acest modul o modifică în loc să o creeze:

- **`inject_relations_into_existing_user()`** — citește `User.java` și injectează relațiile din `relations.csv`:
  - **N:1**: `_inject_n1()` — `@ManyToOne` + `@JoinColumn`
  - **1:1**: `_inject_11()` — `@OneToOne` + `@JoinColumn` + invers în entitatea țintă
  - **N:N**: `_inject_nn()` — `@ManyToMany` + `@JoinTable` (User este întotdeauna owning side)
  - Apelează `_inject_inverse_for_relation()` pentru a adăuga câmpul invers în entitatea țintă

### 4.10 `i18n.py` (312 linii) — Internaționalizare

- **`ask_ollama_translation()`** — folosește un server local Ollama (`localhost:11434`, model `translategemma:4b`) pentru a traduce etichetile UI în limba țintă. Are un sistem de cache în `.ollama_translation_cache.json`.
- **`update_messages_entity()`** — generează mesajele pentru o entitate în toate locale-urile disponibile (citite din `application.properties`):
  - Pentru fiecare entitate: eticheta entității, etichetele câmpurilor, titlurile view-urilor (listă/detalii), intrările de meniu
  - Pentru limba engleză: generează direct
  - Pentru alte limbi: folosește Ollama pentru traducere, cu fallback la engleză dacă traducerea eșuează
  - Adaugă mesaje pentru relații și compuneri (COMPOSITION_1:N)
  - Folosește `append_unique()` pentru a nu duplica intrările în fișierele `.properties`

### 4.11 `migrate.py` (873 linii) — Migrații incrementale

Acest modul permite actualizarea bazei de date când schema entității cambiază, fără să se regenereze totul.

#### Arhitectură adapter:
- **`DatabaseAdapter`** (ABC) — interfața pentru introspecția bazei de date
- **`HSQLDBAdapter`** — citește schema din fișierul `.jmix/hsqldb.script` (format HSQLDB), parsând declarațiile `CREATE TABLE` pentru a obține coloanele existente
- **`PostgreSQLAdapter`** — schelet pentru viitor (folosește `INFORMATION_SCHEMA`)

#### Funcții de detectare:
- **`get_existing_columns_from_changelogs()`** — parasește toate fișierele XML Liquibase pentru a găsi coloanele deja definite pentru o tabelă
- **`detect_missing_columns()`** — compară câmpurile din `entities.csv` cu cele din DB + changelogs → coloane lipsă
- **`detect_dropped_columns()`** — coloane în DB dar nu în entitate (avertisment)
- **`detect_changed_fields()`** — detectează câmpuri adăugate, eliminate, și redenumite (prin compararea tipurilor)
- **`detect_field_metadata_changes()`** — detectează schimbări de tip, nullable, unique
- **`get_executed_changelog_ids()`** — citește ID-urile changesets-urilor executate din `DATABASECHANGELOG`

#### Funcții de generare a changelog-urilor:
- **`gen_add_column_changelog()`** — `addColumn` pentru noi câmpuri
- **`gen_drop_column_changelog()`** — `dropColumn` pentru câmpuri eliminate
- **`gen_rename_column_changelog()`** — `renameColumn` pentru câmpuri redenumite
- **`gen_modify_column_changelog()`** — `modifyDataType`, `addNotNullConstraint`, `dropNotNullConstraint`, `addUniqueConstraint`, `dropUniqueConstraint`

#### Funcție principală: `migrate_entity(name, mode)`
Moduri de operare:
- `"prompt"` — întreabă înainte de drop (default)
- `"force"` — aplică tot fără întrebări
- `"dry-run"` — nu scrie fișiere
- `"quiet"` — doar loghează dacă există schimbări

Pași:
1. Detectează și injectează câmpurile lipsă în fișierul Java existent
2. Actualizează mesajele i18n pentru câmpurile noi
3. Detectează câmpuri eliminate, redenumite, și schimbări de metadata
4. Actualizează în-place fișierul Java pentru redenumiri
5. Generează changelogs pentru fiecare tip de schimbare

---

## 5. Arhitectura datelor și fluxul de lucru

### CSV-uri ca schemă declarativă

| CSV | Rol | Coloane cheie |
|---|---|---|
| `entities.csv` | Câmpurile business | `entity_name`, `field_name`, `field_type`, `mandatory`, `unique` |
| `relations.csv` | Relațiile între entități | `source_entity`, `relation_type`, `target_entity`, `field_name`, `mandatory`, `ownership` |
| `traits.csv` | Trăsături arhitecturale | `entity_name`, `versioned`, `audit_of_creation`, `audit_of_modification`, `soft_delete` |
| `roles.csv` | Control acces RBAC | `name`, `code`, `entity_name`, `ui_list`, `ui_detail`, `create`, `read`, `update`, `delete` |

### Tipuri de relații susținute

| Tip | JPA | UI | Changelog |
|---|---|---|---|
| `N:1` | `@ManyToOne` | `entityComboBox` | `addColumn` + FK |
| `1:N` | `@OneToMany(mappedBy)` | — (în entitatea inversă) | — |
| `1:1` | `@OneToOne` + `@JoinColumn` | `entityComboBox` | `addColumn` + index unique + FK |
| `COMPOSITION_1:N` | `@Composition` + `@OneToMany(mappedBy)` | `dataGrid` în detaliu | FK |
| `COMPOSITION_1:1` | `@Composition` + `@OneToOne` + `@JoinColumn` | — | `addColumn` + index unique |
| `N:N` | `@ManyToMany` + `@JoinTable` | Depinde de `ownership` | `createTable` + FK |

### Ownership pentru N:N

| Valoare | Sursă (owner) | Țintă (inverse) |
|---|---|---|
| `owning` / gol | `multiSelectComboBoxPicker` | `dataGrid` read-only |
| `single-owning` | `multiSelectComboBoxPicker` | Fără UI |
| `both-owning` | `dataGrid` cu add/exclude | `dataGrid` cu add/exclude |

---

## 6. Modul de lucru (Development Workflow)

Conform `AGENTS.md`, workflow-ul este:
1. **Scriere teste** (conform `ai-docs/skills/testing/SKILL.md`)
2. **Verificare probleme IDE** (dacă `idea-mcp` este disponibil)
3. **Rulare teste** (`./gradlew test`)
4. **Verificare UI** (dacă `playwright-mcp` este disponibil)

---

## 7. Observații notabile și potențiale probleme

### Puncte forte
1. **Arhitectură modulară** — fiecare responsabilitate are un modul dedicat (entity, liquibase, views, security, i18n, migrate, user)
2. **CSV-driven** — schema este declarativă și ușor de înțeles/modificat
3. **Dry-run** — mod foarte util pentru validarea schimbărilor fără a modifica proiectul real
4. **Migrații incrementale** — suport foarte avansat pentru detectarea automată a schimbărilor (add/drop/rename/modify)
5. **i18n cu Ollama** — traducere automată folosind un model local
6. **Audit addon auto-configurat** — injectează dependențele și changelog-ul automat
7. **Topological sort** — entitățile sunt generate în ordinea dependențelor

### Aspecte care ar putea fi îmbunătățite
1. **Folosirea `re.sub` cu raw strings pentru înlocuiri** în `cmd_init_project()` (liniile 527, 545, 597) — folosește `re.sub` cu pattern raw string, dar înlocuirea e un string simplu, ceea ce ar putea avea probleme cu backreferințe
2. **Variabile globale modulare** — `COMPANY`, `PROJECT`, `project_name`, `company_path` sunt variabile globale calculate la importare. Pentru dry-run, acestea sunt patch-uite în toate modulele, ceea ce e fragil (dacă se adaugă un modul nou, trebuie adăugat și în lista de patch)
3. **Folosirea `import re` local** în funcțiile din `migrate.py` și `views.py` în loc de import la începutul fișierului
4. **Nu există teste Python** — proiectul are teste Java (`src/test/java`) dar nicio testare a CLI-ului Python
5. **Funcția `detect_changed_fields`** are o linie foarte complexă (linia 390) care este greu de înțeles
6. **`migrate_entity`** are o logică de redenumire a câmpurilor care folosește `next()` cu generatori, ceea ce ar putea ridica `StopIteration` dacă nu găsește tipul

### Conformitate cu AGENTS.md
- Entitățile Java generated au: UUID + `@JmixGeneratedValue`, `@Version` (dacă versioned=true), `@InstanceName` (pe primul String)
- Folosește `DataManager` (în codul Java generat, nu în CLI)
- View-urile folosesc `StandardListView` / `StandardDetailView`
- Securitatea folosește `@ResourceRole`, `@ViewPolicy`, `@MenuPolicy`
- Changelog-urile Liquibase sunt incluse în `changelog.xml`
- Mesajele sunt în toate fișierele locale (messages.properties, messages_en.properties, etc.)
- **Nu există Lombok** pe entități
- **Nu există business logic în view-uri**
- **Nu există text UI hardcodat** — toate etichetele folosesc `msg://`

---

## 8. Concluzie

`jmix-cli.py` este un instrument puternic și bine arhitecturat pentru generarea scaffold-ului unui proiect Jmix 2.7.x din fișiere CSV. Are o arhitectură modulară clară, suport avansat pentru migrații incrementale, și funcționalități sofisticate precum dry-run și traducere automată cu Ollama. Proiectul respectă bine standardele Jmix și are o abordare declarativă prin CSV-uri care face ca modificarea schemei de date să fie foarte simplă.

Principalii factori de risc sunt: lipsa de teste Python pentru CLI, dependența de variabile globale pentru dry-run, și câteva expresii complexe de regex care ar putea fi greu de întreținut.
