# Analiza Proiectului AgilePM și Scriptului `jmix-cli.py`

---

## 1. Arhitectura Proiectului

**AgilePM** este un proiect demonstrativ Jmix 2.7.x (Java 17, Spring Boot, Vaadin Flow) pentru gestionarea proiectelor agile. Proiectul folosește HSQLDB ca bază de date de dezvoltare și rulează pe `http://localhost:8080` cu credențiale `admin/admin`.

**Structura proiectului:**
- `/src/main/java/com/company/agilepm/` — cod sursă Java
- `/src/main/resources/com/company/agilepm/` — resurse (views XML, Liquibase, menu)
- **Fișiere CSV de configurare:** `traits.csv`, `entities.csv`, `relations.csv`, `roles.csv`
- **Script principal:** `jmix-cli.py` — generator parametric de cod

---

## 2. Modelul de Domeniu (9 entități)

| Entitate | Câmpuri | Trăsături |
|----------|---------|-----------|
| **Project** | name, startDate | versioned, audit, soft-delete |
| **Milestone** | title, targetDate | versioned, audit |
| **Task** | subject, dueDate | versioned, audit, soft-delete |
| **TaskComment** | content | versioned |
| **Priority** | level | versioned |
| **UserProfile** | phoneNumber | versioned, audit |
| **UserConfig** | theme | versioned |
| **Team** | name | versioned, audit |
| **Client** | companyName | versioned, audit, soft-delete |

**Tipuri de relații** (din `relations.csv`):
- **COMPOSITION_1:N** — Milestone → Project, TaskComment → Task (cascade delete)
- **COMPOSITION_1:1** — UserConfig → UserProfile (cascade delete)
- **N:1** — Task → Milestone, Task → User/Priority, TaskComment → Task/User, User → Team, UserProfile → User
- **N:N** — Team ↔ Client (tabel de legătură `TEAM_CLIENT_LINK`)

---

## 3. Analiza Scriptului `jmix-cli.py` (2899 linii Python)

### 3.1 Scopul Principal

`jmix-cli.py` este un **generator parametric de cod Jmix** care citește fișiere CSV și generează:
- Clase Java entity (`@JmixEntity`, `@Entity`, `@Version`, audit, soft-delete)
- Changelog-uri Liquibase (tabele, coloane, FK constraints, indexuri unice)
- View-uri FlowUI (list-view.xml + ListView.java, detail-view.xml + DetailView.java)
- Mesaje i18n (`messages.properties`, `messages_ro.properties`) cu traducere automată via Ollama
- Roluri de securitate Jmix (`@ResourceRole`)
- Injectări automate în `User.java` și view-urile existente

### 3.2 Comenzile Disponibile

| Comandă | Acțiune |
|---------|---------|
| `python3 jmix-cli.py init <nume> <group> [lang]` | Clonează template-ul Jmix, refactorizează pachetele |
| `python3 jmix-cli.py entity-all` | Generează toate entitățile + changelog-uri |
| `python3 jmix-cli.py entity <Nume>` | Generează o singură entitate |
| `python3 jmix-cli.py ui-list-all` | Generează toate list view-urile |
| `python3 jmix-cli.py ui-detail-all` | Generează toate detail view-urile |
| `python3 jmix-cli.py security` | Generează rolurile de securitate |
| `python3 jmix-cli.py build-all` | Generare completă (toate etapele) |

### 3.3 Fluxul de Execuție `build-all`

```
PHASE 1: Entități + Liquibase + Mesaje (topologic sortate)
  → Generează clase Java entity
  → Generează changelog-uri de bază (-01_base-<entity>.xml)
  → Generează changelog-uri de relații (-02-relations_<entity>.xml)
  → Injectează relații în User.java (pentru N:1)
  → Generează mesaje i18n (en + ro)

PHASE 2.5: Finalizare relații COMPOSITION_1:1
  → Injectează @Composition în entity sorță
  → Injectează mappedBy invers în entity țintă
  → Generează changelog FK (-03-fk-<entity>.xml)

PHASE 2: View-uri FlowUI
  → Generează list-view.xml + ListView.java
  → Generează detail-view.xml + DetailView.java
  → Injectează UI pentru COMPOSITION_1:N în view-ul părintelui
  → Injectează relații N:1 în User.java views
  → Actualizează menu.xml

PHASE 3: Securitate
  → Generează interfețe @ResourceRole din roles.csv
```

### 3.4 Componente Cheie

**Funcția `get_sorted_entities_by_dependency()`** — efectuează sortare topologică a entităților bazată pe dependențele din `relations.csv`, cu protecție împotriva ciclurilor și self-referencing.

**Funcția `gen_entity_mechanic_from_csv()`** — generează clasa Java entity completă cu:
- `@JmixEntity`, `@Entity`, `@Table` cu indexuri unice
- Câmpuri de sistem (ID UUID, VERSION, audit, soft-delete)
- Câmpuri de business din `entities.csv`
- Relații JPA (N:1, 1:N, 1:1, N:N)
- Gettere și settere

**Funcția `inject_relations_into_existing_user()`** — injectează proprietăți N:1 în `User.java` (extinderea entității standard Jmix User).

**Funcția `update_messages_entity()`** — generează mesaje i18n pentru toate limbile din `application.properties`, cu traducere automată prin Ollama (`translategemma:4b`) pentru limbile non-engleze.

---

## 4. Observații și Probleme Identificate

### 4.1 Probleme de Design

1. **Fișier uriaș monolit** — `jmix-cli.py` are 2899 linii într-un singur fișier. Lipsa modularizării (entități, views, security, i18n ar trebui să fie module separate).

2. **Cod duplicat masiv** — logica de `COMPOSITION_1:1` apare de 3-4 ori (în `gen_entity_mechanic_from_csv`, `build-all` PHASE 2.5, și alte locuri). Aceasta crește riscul de inconsistență.

3. **Hardcoded paths** — `PROIECT_PATH` este calculat din `Path.cwd()`, iar multe construcții de path folosesc concatenare de string-uri (`+`) în loc de `os.path.join()` sau `pathlib`.

4. **Lipsa de validare** — nu există validări pentru:
   - Integrity constraint-urile CSV (ex: entități duplicate, tipuri necunoscute)
   - Corectitudinea relațiilor (ex: FK către entități inexistente)
   - Codul Java generat (nu se compilează automat după generare)

5. **Gestiunea erorilor slabă** — multe excepții sunt prinse generic cu `except Exception`, iar unele erori doar afișează un mesaj și continuă execuția.

6. **Problema `to_camel_case_lower()`** — funcția convertor este folosită pentru `mapped_by` în relațiile 1:N, dar logica este inconsistentă (ex: `UserProfile` → `userProfile`, dar pentru 1:1 composition folosește `to_camel_case_lower(src_class)` care poate genera nume greșite).

### 4.2 Probleme de Siguranță

7. **Injecție de cod prin manipulare de fișiere** — scriptul scrie direct în fișiere `.java` și `.xml` folosind `replace()` pe string-uri. Dacă un fișier a fost modificat manual, injectările pot faila sau corupe fișierul.

8. **`User.java` hardcoded** — relațiile pentru `User` sunt hardcodate să funcționeze doar cu `N:1`. Orice alt tip de relație pentru `User` (ex: `1:1`, `N:N`) este ignorată.

9. **Import injection duplicat** — funcția `inject_import_if_missing()` caută doar un singur `package ...;` și adaugă importul, dar dacă există deja importul în altă locație, nu-l detectează corect.

### 4.3 Probleme de Funcționalitate

10. **Traduceri Ollama blochează generarea** — dacă Ollama nu rulează, traducerile pentru limbile non-engleze cad înapoi la engleză, dar mesajul de avertizare apare pentru fiecare câmp (output foarte voluminoas).

11. **Lipsa de idempotență parțială** — deși există verificări `if ... not in content`, generarea repetată poate duplica conținut în anumite cazuri (ex: relații inverse în 1:1).

12. **Timestamp-uri în changelog** — toate changelog-urile folosesc `datetime.now()` la rulare, deci rulări repetate în aceeași secundă pot genera fișiere cu același timestamp, cauzând conflicte Liquibase.

13. **`entities.csv` fallback la `["name"]`** — dacă `entities.csv` nu are rânduri pentru o entitate, se folosește `computed_traits_list = ["name"]`, care este un nume de câmp inexistent, generând mesaje i18n greșite.

---

## 5. Puncte Forte

- **Arhitectură declarativă prin CSV** — separarea modelului de configurație de logica de generare
- **Suport pentru toate tipurile de relații JPA** — N:1, 1:N, 1:1, N:N, plus COMPOSITION
- **Gestiune automată a dependențelor** — sortare topologică pentru ordinea corectă de generare
- **Extinderea `User.java`** — gestionează corect entitatea sistem Jmix
- **i18n cu traducere automată** — integrare Ollama pentru localizare
- **Generare de securitate** — roluri complete cu `@ResourceRole`, `@EntityPolicy`, `@ViewPolicy`, `@MenuPolicy`

---

## 6. Recomandări

1. **Refactorizare în module** — separă scriptul în module: `entity.py`, `liquibase.py`, `views.py`, `security.py`, `i18n.py`
2. **Validare CSV** — adaugă validare la început pentru toate fișierele CSV (schema, tipuri, referințe)
3. **Testare automată** — adaugă teste pentru a verifica că codul generat este compilabil
4. **Idempotență** — folosește un mechanism de locking/tracking pentru a evita duplicate
5. **Path handling** — folosește `pathlib` consistent pentru toate operațiile cu fișiere
6. **Elimină codul duplicat** — extrasă logica de `COMPOSITION_1:1` într-o funcție comună
7. **Compilare automată** — opțiune pentru a compila automat după generare (`./gradlew compileJava`)
