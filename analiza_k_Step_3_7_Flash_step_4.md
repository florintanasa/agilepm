# Analiză proiect AgilePM + `jmix-cli.py` — Step 4

## 1. Context general al proiectului

Proiectul `agilepm` este un **proiect Jmix 2.7.x** (Java 17, Spring Boot, Vaadin Flow) conceput ca „sample” / scaffolding industrial pentru o aplicație de gestionare a proiectelor agile. În directorul rădăcină se află:

- **Fișiere CSV de definire a modelului**: `entities.csv`, `relations.csv`, `traits.csv`, `roles.csv`
- **Script Python `jmix-cli.py`** + pachet `jmix_cli/` — generatorul de cod care citește CSV-urile și produce toate layerele Jmix
- **Structură Jmix standard**: `src/main/java/...`, `src/main/resources/...`, `build.gradle`, `settings.gradle`
- **Fișiere de analiză**: mai multe fișiere `analiza_k_Step_3_7_Flash*.md` (probabil rezultate de rulări anterioare ale CLI-ului)

---

## 2. Structura `jmix-cli.py` și module

### `jmix-cli.py` (entry-point, 31 linii)
Doar un wrapper care apelează `main()` din `jmix_cli/cli.py`.

---

### `jmix_cli/cli.py` (625 linii) — orchestratorul principal

Acesta este **inauncher-ul CLI** cu două mari ramuri:

**a) `init <project_name> <target_group> [locale]`**
- Clonează template-ul `florintanasa/jmix-ai-template` (branch `v2.8.2`)
- Șterge istoricul Git
- Refactorizează package-ul din `io.jmix.tempate` în `<target_group>.<project_name>`
- Injectează dependența de traduceri Jmix în `build.gradle` dacă s-a cerut altă limbă decât `en`
- Actualizează `application.properties` cu `jmix.core.available-locales`
- Generează fișiere `messages.properties` și `messages_<lang>.properties`
- Face replace la toate fișierele `.java`, `.xml`, `.properties`
- Inițializează un repo Git nou
- Setează permisiunea `gradlew`

**b) Fără `init` — rulare în interiorul unui proiect Jmix existent**

Acțiuni disponibile:
- `entity <Name>` — generează o entitate single + changelog + mesaje
- `entity-all` — generează toate entitățile în ordinea dependințelor
- `ui-list <Name>` / `ui-list-all` — liste
- `ui-detail <Name>` / `ui-detail-all` — detalii
- `security` — roluri
- `build-all` — pipeline complet în 3 faze

Pipeline-ul `build-all`:
1. **Phase 1**: Entități Java + Liquibase base + relationships (N:1, 1:1, N:N, COMPOSITION)
2. **Phase 1.5/1.6/1.7**: Finalizări relații `COMPOSITION_1:1`, injectări în `User.java`
3. **Phase 2**: View-uri XML + Java (list + detail) + menu.xml
4. **Phase 3**: Security roles din `roles.csv`

---

### `jmix_cli/utils.py` (121 linii) — utilitare

- Detectează automat `PROJECT` din `settings.gradle` și `COMPANY` din `build.gradle`
- `to_camel_case_lower()` — convertire în camelCase lower-first
- `inject_import_if_missing()` — injectează importuri în fișiere Java (înlocuiește `package ...;`)
- `validate_csv_path()` — validează că CSV-ul are coloanele necesare (ridică excepție dacă lipsesc)
- `write_file()` — scrie fișier cu creare automată de directoare
- `append_unique()` — adaugă linii în fișiere `.properties` fără duplicate (folosit pentru i18n)

---

### `jmix_cli/entity.py` (541 linii) — generator de entități JPA/Jmix

Funcționalități:
- **`get_traits_from_csv()`** — citește `traits.csv`: `versioned`, `audit_of_creation`, `audit_of_modification`, `soft_delete`
- **`get_entities_from_csv()`** — citește `entities.csv`: fields cu tip, mandatory, unique
- **`_build_imports_and_fields()`** — construiește:
  - Câmpuri și metode pentru `@Version`, `@CreatedBy`, `@CreatedDate`, `@LastModifiedBy`, `@LastModifiedDate`, `@DeletedBy`, `@DeletedDate`
  - Câmpuri de business cu `@Column`, `@NotNull`, `@InstanceName` (primul String devine `@InstanceName`)
  - `@Index` pentru câmpuri unique
- **`_build_relation_fields_and_methods()`** — construiește câmpuri relaționale:
  - `N:1` → `@ManyToOne` + `@JoinColumn`
  - `1:N` → `@OneToMany(mappedBy=...)`
  - `1:1` → `@OneToOne` + `@JoinColumn` + injectează automat **inversa** în target
  - `N:N` → `@ManyToMany` + `@JoinTable` + suport pentru `ownership=both-owning`
- **`_inject_composition_into_parent()`** — injectează `@Composition` în entitatea țintă (parent):
  - `COMPOSITION_1:N` → `@OneToMany(mappedBy=...)`
  - `COMPOSITION_1:1` → `@OneToOne` + `@JoinColumn` + injectează invers în copil
- **`get_relations_from_csv()`** — citește `relations.csv`, suportă `ownership` opțional
- **`get_sorted_entities_by_dependency()`** — **topological sort** bazat pe dependențele din `relations.csv` (N:1, 1:1, 1:N) → entitățile fără dependențe sunt generate primele
- **`gen_entity_mechanic_from_csv()`** — asamblează totul și scrie fișierul `.java` în `entity/`

---

### `jmix_cli/liquibase.py` (259 linii) — changelog-uri Liquibase

- **`map_type()`** — mapă tipuri Java → tipuri SQL (HSQLDB-friendly)
- **`gen_liquibase_changelog_from_csv()`** — generează `01-base-<entity>.xml` cu:
  - `createTable` cu coloane ID, VERSION, audit, business
  - `createIndex` pentru câmpuri unique
- **`gen_liquibase_relations_changelog()`** — generează `02-relations-<entity>.xml` cu:
  - `N:1` → `addColumn` + `addForeignKeyConstraint`
  - `1:1` / `COMPOSITION_1:1` → `addColumn` + `createIndex` (unique) + `addForeignKeyConstraint`
  - `N:N` → `createTable` pentru join table + 2 FK-uri + PK
  - Tratare specială pentru tabelul `USER` → `USER_` (rezervat HSQLDB)

---

### `jmix_cli/views.py` (733 linii) — view-uri FlowUI (XML + Java)

- **`gen_list_view_from_csv()`** — generează `*-list-view.xml` + `*ListView.java`:
  - DataGrid cu coloane pentru fiecare field
  - FetchPlan cu proprietățile din relațiile N:1 / 1:1 / N:N
  - Acțiuni CRUD standard
- **`gen_detail_view_from_csv()`** — generează `*-detail-view.xml` + `*DetailView.java`:
  - Form fields: `checkBox` pentru boolean, `datePicker` pentru date, `textField` pentru restul
  - Pentru relații N:1/1:1 → `entityComboBox` cu lookup/open/clear
  - Pentru N:N → `multiSelectComboBoxPicker`
  - **După generare**, apelează `_inject_composition_ui_into_parent()` care injectează UI de COMPOSITION_1:N în view-ul părintelui (dataGrid cu create/edit/remove)
- **`inject_list_ui_into_existing_user()`** — modifică `user-list-view.xml` pentru relațiile User-ului
- **`inject_detail_ui_into_existing_user()`** — modifică `user-detail-view.xml` cu containere colecție și comboBox-uri
- **`inject_nn_grid_into_inverse_entity()`** — injectează `dataGrid` în view-ul entității **inverse** pentru N:N (pentru `ownership=owning` / `both-owning`)
- **`inject_nn_datagrid_into_source_entity()`** — pentru `both-owning`: mută colecția în interiorul `<instance>`, elimină `multiSelectComboBoxPicker` și adaugă `dataGrid` cu acțiuni add/exclude în source detail view
- **`_infer_inverse_n_n_field()`** — folosește regex pe fișierul Java al entității inverse pentru a găsi numele câmpului `mappedBy`

---

### `jmix_cli/i18n.py` (308 linii) — localizare automată

- **`update_messages_entity()`**:
  - Citește `application.properties` pentru a afla `jmix.core.available-locales`
  - Pentru fiecare entitate, generează chei i18n în `messages_en.properties` + `messages_<locale>.properties`
  - Chei: entity labels, field labels, view titles (list/detail), menu labels, relation labels, composition UI labels
  - **Pentru `en`**: generează direct cu texte engleze (ex: "Project", "Created by")
  - **Pentru alte limbi**: apelează `ask_ollama_translation()` pentru a traduce fiecare label prin Ollama (`translategemma:4b`)
- **Cache traduceri**: `.ollama_translation_cache.json` — persistență locală pentru a nu re-traduce la fiecare rulare
- **Fallback Engleza**: dacă Ollama eșuează, revine la textul englezesc
- **Tratare specială RO**: dacă traducerea e prea lungă, folosește template-uri predefinite ("Lista X", "Detalii X")

---

### `jmix_cli/security.py` (130 linii) — roluri Jmix

- **`gen_jmix_resource_roles_from_csv()`**:
  - Grupează politicile după `code` din `roles.csv`
  - Generează `@ResourceRole(name=..., code=..., scope=SecurityScope.UI)`
  - Pentru fiecare politică:
    - `@ViewPolicy(viewIds = {...})` pentru list/detail
    - `@MenuPolicy(menuIds = {...})` pentru list view
    - `@EntityPolicy(entityClass=X.class, actions={...})` pentru CRUD
    - `@EntityAttributePolicy(entityClass=X.class, attributes="*", action=VIEW|MODIFY)`
  - Numele clasei: kebab-case → PascalCase + sufix `Role`

---

### `jmix_cli/user.py` (208 linii) — relații în entitatea `User` (built-in Jmix)

- **`inject_relations_into_existing_user()`** — injectează relații din `relations.csv` în `User.java`:
  - `N:1` → `_inject_n1()` — `@ManyToOne` + `@JoinColumn`
  - `1:1` → `_inject_11()` — `@OneToOne` + `@JoinColumn`
  - `N:N` → `_inject_nn()` — **proprie logică de `@JoinTable`** cu nume fix `USER_<TARGET>_LINK`
- **`_inject_inverse_for_relation()`** — injectează câmpul invers în entitatea țintă:
  - `1:1` → invers este mereu `private User user;` cu `mappedBy`
  - `N:N` → suportă `owning`, `single-owning`, `both-owning` (același model ca în `entity.py`)

---

## 3. Fluxul de lucru prevăzut

```
┌─────────────────────────────────────────────────────────────┐
│  1. CSV-uri în directorul rădăcină:                        │
│     entities.csv, relations.csv, traits.csv, roles.csv     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  python jmix-cli.py build-all                               │
│  ─────────── sau comenzi individuale ─────────────          │
└──────────────────────┬──────────────────────────────────────┘
                       │
   ┌───────────────────┼────────────────────┐
   ▼                   ▼                     ▼
entities.csv     relations.csv          traits.csv
   │                   │                     │
   ▼                   ▼                     ▼
Entități JPA      RELAȚII +            @Version, audit,
+ imports         Liquibase FK          soft-delete
   │                   │                     │
   └───────────────────┼────────────────────┘
                       ▼
              View-uri FlowUI
              (XML + Java)
                       │
                       ▼
                 menu.xml
                       │
                       ▼
               Security roles
                       │
                       ▼
               i18n (messages.properties)
              + traduceri Ollama
```

---

## 4. Puncte forte

| Aspect | Detalii |
|--------|---------|
| **Declarativ** | Totul se definește în CSV-uri simple, fără cod Java manual |
| **Orchestrare completă** | `build-all` face totul: entități, DB, UI, securitate, i18n |
| **Topological sort** | Entitățile sunt generate în ordinea dependințelor (ex: `Priority` înainte de `Task`) |
| **Suport relații complexe** | N:1, 1:1, N:N (cu ownership: owning, single-owning, both-owning), COMPOSITION_1:N, COMPOSITION_1:1 |
| **Tratare `User` built-in** | Logică specială pentru a injecta relații în `User.java` fără a-l suprascrie |
| **i18n automat** | Cu cache local + Ollama, fără a re-traduce la fiecare rulare |
| **Injecție idempotentă** | Verifică dacă câmpurile/importurile există deja înainte de a injecta |

---

## 5. Îngrijorări / limite

| Problemă | Detalii |
|-----------|---------|
| **Hardcodări în interiorul modulelor** | `COMPANY` și `project_name` sunt constante globale în `utils.py` bazate pe directorul curent (`Path.cwd()`). Dacă CLI-ul se rulează din altă locație, nu merge. |
| **Lipsa package `jmix_cli/__init__.py`** | Nu am văzut un `__init__.py` — posibil că nu este un pachet Python complet, dar funcționează ca modul dacă directorul este în `PYTHONPATH` |
| **Regex fragil în `inject_import_if_missing`** | Înlocuiește exact `package ...;` — dacă fișierul Java are spații diferite, nu funcționează |
| **`inject_nn_datagrid_into_source_entity` mută containere în `<instance>`** | Logică destul de complexă cu `re.sub` și înlocuiri string — poate distruge XML-ul dacă structura se schimbă |
| **Traduceri Ollama hardcodate pentru `en` vs `ro`** | `ask_ollama_translation` are fallback-uri hardcodate doar pentru `ro` (`"Lista X"`, `"Detalii X"`) |
| **`settings.gradle` / `build.gradle` trebuie să existe** | CLI-ul nu funcționează în afara unui proiect Jmix (ceea ce este logic, dar nu este validat foarte frumos) |
| **`User` ca entry în `entities.csv` nu este necesar** | Relațiile lui `User` se citesc din `relations.csv`, dar logica este duplicată în mai multe locuri |
| **`validate_csv_path` ridică excepție** | Uneori în `cli.py` se folosește, alteori nu — lipsa de validare consistentă |
| **Lipsa logging/structured output** | Toate mesajele sunt `print()` — greu de capturat în CI/CD |
| **Mutabilitate globală în `utils.py`** | `PROJECT`, `COMPANY` etc. se calculează o dată la import — dacă directorul se schimbă, valorile rămân |
| **`inject_nn_datagrid_into_source_entity` hardcodează `com.company.agilepm`** | Linia 531: `msg://com.company.agilepm.view....` — ar trebui să folosească `COMPANY` și `project_name` |

---

## 6. Recomandări rapide

1. **Adaugă `jmix_cli/__init__.py`** pentru claritate și importuri corecte
2. **Înlocuiește `print()` cu `logging`** pentru output controlabil
3. **Extrage constantele `com.company.agilepm`** din `views.py` linia 531 în variabile bazate pe `COMPANY`/`project_name`
4. **Adaugă validări CSV coerente** înainte de fiecare etapă majoră (nu doar când apare eroare)
5. **Adaugă un flag `--dry-run`** pentru a genera fișierele într-un temp și a le afișa, fără a rescrie proiectul
6. **Centralizează logica de `User`** — este împrăștiată în `cli.py`, `entity.py`, `user.py`, `views.py`
