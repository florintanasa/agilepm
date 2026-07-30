# Agile Project Management System

A Jmix 2.7.x-based full-stack application for managing agile projects with entities, relationships, and role-based access control.  
This application is a demo for how to use Jmix CLI Tool. 

## Architecture Overview 

```mermaid
classDiagram
    direction LR
    
    class Project {
        +UUID id
        +String name
        +LocalDate startDate
        +List<Milestone> milestones
    }
    class Milestone {
        +UUID id
        +String title
        +LocalDate targetDate
        +Project project
    }
    class Task {
        +UUID id
        +String subject
        +LocalDate dueDate
        +Milestone milestone
        +User assignee
        +Priority priority
        +List<TaskComment> comments
    }
    class TaskComment {
        +UUID id
        +String content
        +Task task
        +User author
    }
    class Priority {
        +UUID id
        +String level
    }
    class User {
        +UUID id
        +String username
        +String firstName
        +String lastName
        +Team team
        +UserProfile profile
        +List<Priority> priorities
    }
    class UserProfile {
        +UUID id
        +String phoneNumber
        +User user
    }
    class UserConfig {
        +UUID id
        +String theme
    }
    class Team {
        +UUID id
        +String name
        +List<Client> clients
    }
    class Client {
        +UUID id
        +String companyName
    }

    Project "1" *-- "N" Milestone : COMPOSITION
    Milestone "N" --> "1" Project : FK project_id
    Task "N" --> "1" Milestone : FK milestone_id
    Task "1" *-- "N" TaskComment : COMPOSITION
    TaskComment "N" --> "1" Task : FK task_id
    Task "N" --> "1" User : FK assignee_id
    Task "N" --> "1" Priority : FK priority_id
    TaskComment "N" --> "1" User : FK author_id
    User "N" --> "1" Team : FK team_id
    User "1" --> "1" UserProfile : FK profile_id
    UserProfile "1" --> "1" User : FK user_id
    UserProfile "1" *-- "1" UserConfig : COMPOSITION
    User "N" -- "N" Priority : USER_PRIORITY_LINK
    Team "N" -- "N" Client : TEAM_CLIENT_LINK
```

## Domain Model

The system consists of 9 custom entities built on top of the standard Jmix `User` entity:

### Core Entities

| Entity | Description | Fields |
|--------|-------------|--------|
| **Project** | Root aggregate for project management | name, startDate (with versioning, audit, soft-delete) |
| **Milestone** | Project milestone with target date | title, targetDate |
| **Task** | Work item with assignee and priority | subject, dueDate, assignee, priority |
| **TaskComment** | Comments on tasks (composition) | content, author, task |
| **Priority** | Task priority levels | level |

### Organization Entities

| Entity | Description | Fields |
|--------|-------------|--------|
| **Team** | Development team | name |
| **Client** | Client organization | companyName |
| **User** | Extended from Jmix User | username, firstName, lastName, team (N:1), profile (1:1), priorities (N:N) |
| **UserProfile** | User profile (1:1 with User) | phoneNumber, user |
| **UserConfig** | User preferences (composition with UserProfile) | theme, profile |

### Relationship Types

- **COMPOSITION (1:N, 1:1)**: Parent-child relationship where child lifecycle is tied to parent. Deleting parent cascades to children.
- **ASSOCIATION (N:1, 1:1)**: Regular relationship without cascade delete. For 1:1, both sides are defined in `relations.csv` so each entity gets a bidirectional navigation property.
- **MANY_TO_MANY**: Implemented via junction table. The `ownership` column controls how the UI is generated:
  - `owning` / empty: source entity gets a `multiSelectComboBoxPicker` in the detail view, inverse target gets a read-only `dataGrid`.
  - `single-owning`: source entity gets a `multiSelectComboBoxPicker`; target entity gets **no relationship UI** at all.
  - `both-owning`: both sides get a `dataGrid` with add/remove actions, and the `multiSelectComboBoxPicker` is removed.

## Configuration Files

### traits.csv - Entity Traits Configuration

Defines architectural properties for each entity:

| Column | Description |
|--------|-------------|
| `entity_name` | Entity class name |
| `versioned` | Enable optimistic locking via @Version |
| `audit_of_creation` | Add CreatedBy/CreatedDate fields |
| `audit_of_modification` | Add LastModifiedBy/LastModifiedDate fields |
| `soft_delete` | Enable soft delete via @DeletedBy/@DeletedDate |

### entities.csv - Entity Attributes Configuration

Defines custom business attributes for entities:

| Column | Description |
|--------|-------------|
| `entity_name` | Entity class name |
| `field_name` | Property name |
| `field_type` | Java type (String, Integer, LocalDate, etc.) |
| `mandatory` | NOT NULL constraint |
| `unique` | UNIQUE constraint |

### relations.csv - Entity Relationships Configuration

Defines relationships between entities:

| Column | Description |
|--------|-------------|
| `source_entity` | Source entity class name |
| `relation_type` | COMPOSITION_1:N, COMPOSITION_1:1, N:1, 1:1, N:N |
| `target_entity` | Target entity class name |
| `field_name` | Field name in source entity |
| `mandatory` | NOT NULL constraint on FK column |
| `ownership` | For N:N only: `owning` (source owns junction table, target is read-only), `single-owning` (source owns junction table, target has no UI), `both-owning` (both sides own), empty/omit for inverse/mappedBy |

> Note: For `1:1`, the relation is defined **twice**: once from the source side with `field_name`, and once from the target side with the inverse `field_name`. This ensures bidirectional navigation on both sides.

### roles.csv - Security Roles Configuration

Defines role-based access control:

| Column | Description |
|--------|-------------|
| `name` | Display name of the role |
| `code` | Unique role identifier |
| `entity_name` | Entity this role applies to |
| `ui_list` | Grant access to list view |
| `ui_detail` | Grant access to detail view |
| `create` | Grant CREATE permission |
| `read` | Grant READ permission |
| `update` | Grant UPDATE permission |
| `delete` | Grant DELETE permission |

## Jmix CLI Tool

`jmix-cli.py` is a parametric code generator that creates Jmix entities, views, Liquibase changelogs, messages, and security roles from CSV configuration files.

### Installation

```bash
# Install in editable mode
pip install -e .
# Run via entry point
jmix-cli --help
# Or directly
python jmix-cli.py --help
```

### Usage

```bash
# Generate ALL entities + Liquibase changelogs
python3 jmix-cli.py entity-all

# Generate single entity
python3 jmix-cli.py entity <EntityName>

# Generate ALL list views
python3 jmix-cli.py ui-list-all

# Generate ALL detail views
python3 jmix-cli.py ui-detail-all

# Generate single view
python3 jmix-cli.py ui-list <EntityName>
python3 jmix-cli.py ui-detail <EntityName>

# Generate security roles
python3 jmix-cli.py security

# Full generation (all phases)
python3 jmix-cli.py build-all
```

## Python Package

The `jmix-cli` command is distributed as a Python package defined by `pyproject.toml`:

- **Build backend:** `setuptools`
- **Python:** >= 3.10
- **Dependencies:** stdlib only (`http.client`, `json`, `csv`, `pathlib`, etc.)
- **Entry point:** `jmix-cli = "jmix_cli.cli:main"`

After `pip install -e .`, the tool is available as `jmix-cli` anywhere on the PATH.

### Error Handling

The CLI uses a centralized exception hierarchy (`jmix_cli/exceptions.py`) instead of scattering `sys.exit()` through generators:

- `JmixCliError` — base
- `ConfigurationError` — missing/invalid project or CSV
- `GenerationError` — code generation failures
- `UserInputError` — bad arguments or missing parameters
- `InvalidCsvError` — CSV missing or schema mismatch

All module-level errors are raised as exceptions. `cli.py` catches them in one place and logs a consistent message before exiting.

### Generated Artifacts

Running `build-all` creates:

1. **Entity classes** (`src/main/java/.../entity/`)
   - UUID primary key with `@JmixGeneratedValue`
   - `@Version` field for optimistic locking (if versioned=true)
   - Audit fields (`createdBy`, `createdDate`, `lastModifiedBy`, `lastModifiedDate`)
   - Soft delete fields (`deletedBy`, `deletedDate`) if soft_delete=true

2. **Liquibase changelogs** (`src/main/resources/.../liquibase/changelog/YYYY/MM/`)
   - Base changelog: `YYYYMMDD-HHMMSS-<entity>-base.xml`
   - Relations changelog: `YYYYMMDD-HHMMSS-<entity>-relations.xml`
   - FK constraint changelog: `YYYYMMDD-HHMMSS-<entity>-fk.xml`
   - The master `changelog.xml` is updated with explicit `<include>` statements in dependency order after generation, ensuring entities are created before their foreign keys and relation tables
   - Audit changelog: automatically includes `/io/jmix/audit/liquibase/changelog.xml` if `traits.csv` enables `audit_of_creation` or `audit_of_modification`

3. **Views** (`src/main/java/.../view/`)
    - List views extending `StandardListView`
    - Detail views extending `StandardDetailView`
    - DataGrid columns for all fields
    - N:N detail views depend on `ownership`:
      - `owning` / empty: source gets `multiSelectComboBoxPicker`, inverse target gets a read-only `dataGrid`
      - `single-owning`: source gets `multiSelectComboBoxPicker`, target gets **no relationship UI**
      - `both-owning`: both sides get `dataGrid` with add/remove actions; the `multiSelectComboBoxPicker` is removed

4. **Messages** (`messages.properties`, `messages_ro.properties`)
    - Entity labels and field names
    - View titles and menu entries
    - For translate is used local `ollama` with model `translategemma:4b`, if was installed

5. **Security Roles** (`src/main/java/.../security/`)
    - `@ResourceRole` annotated classes
    - Entity policies (CRUD)
    - View policies (list/detail)
    - Menu policies for navigation

6. **Gradle dependencies** (`build.gradle`)
    - Automatically injects `io.jmix.audit:jmix-audit-starter` and `io.jmix.audit:jmix-audit-flowui-starter` when `traits.csv` enables audit for any entity
    - Marked with `// Automatically configured via Jmix CLI`
    - Liquibase master changelog gets `<include file="/io/jmix/audit/liquibase/changelog.xml"/>` automatically if missing

### Audit Addon

When `traits.csv` enables `audit_of_creation=true` or `audit_of_modification=true` for any entity, Jmix CLI automatically configures the addon so entity methods like `@CreatedBy`, `@CreatedDate`, `@LastModifiedBy`, and `@LastModifiedDate` work without manual setup:

- Adds to `build.gradle`:
  - `implementation 'io.jmix.audit:jmix-audit-starter'`
  - `implementation 'io.jmix.audit:jmix-audit-flowui-starter'`
- Adds to `src/main/resources/.../liquibase/changelog.xml`:
  - `<include file="/io/jmix/audit/liquibase/changelog.xml"/>`

This creates the underlying `AUDIT_LOGGED_ENTITY` schema automatically via Liquibase and enables the Audit UI screens.

### migrate / migrate-all

```bash
# Incremental migration for one entity
python3 jmix-cli.py migrate <EntityName>

# Incremental migration for all entities from entities.csv
python3 jmix-cli.py migrate-all
```

> [!WARNING]
> `migrate` and `migrate-all` work **only against the current project**. They are not compatible with `--dry-run`, because the dry-run temp directory does not contain the `.jmix/` database state. Without that state, incremental migration cannot determine real missing/renamed/dropped columns.

What they do:
- Inspect the existing database schema via `.jmix/hsqldb.script` and existing Liquibase changelogs
- Compare it against `entities.csv` and `relations.csv`
- Inject missing fields into existing `.java` entity files
- Remove dropped fields from existing `.java` entity files (field declaration, annotations, getter, and setter) when the user confirms the drop
- Generate incremental Liquibase changelogs for:
  - new columns
  - dropped columns (with confirmation prompt)
  - renamed fields, changed types, changed `mandatory`/`unique` constraints

Notes:
- **User entity support**: `migrate-all` now includes the built-in `User` entity. Custom fields added to `entities.csv` for `User` are injected into `User.java`, and incremental changelogs are generated with the correct `USER_` table name. Standard Jmix User fields (`username`, `firstName`, `lastName`, `email`, `active`, `timeZoneId`) are never dropped.
- **Changelog-aware detection**: `detect_dropped_columns` combines columns from both the live database (`.jmix/hsqldb.script`) and existing Liquibase changelog XML files, so dropped columns are detected even when no database is running. Changelogs are processed in filename order to correctly track add→drop→re-add sequences.
- **Already-dropped exclusion**: `_get_already_dropped_columns` parses existing `dropColumn` changesets to prevent re-detecting and re-dropping the same column across multiple `migrate` runs.
- **Duplicate prevention**: New fields are deduplicated by name (case-insensitive) before changelog generation to prevent duplicate Liquibase changesets. Re-added fields (added, dropped, then re-added to `entities.csv`) are correctly handled without generating duplicate addField changelogs.
- **Rename detection**: The tool compares previous field names from existing generated files; a rename is only detected when the old and new field names share at least 3 characters of common prefix (e.g. `firstName` → `firstName2`), preventing false positives when unrelated fields of the same type are added or removed.
- **Metadata change detection**: `detect_field_metadata_changes` scans backward to the previous `private` field declaration to determine the annotation block boundary, preventing false-positive `@NotNull` detection when adjacent fields have `@NotNull`.
- **Unique constraint synchronization**: When `unique` changes in `entities.csv`, `migrate`/`migrate-all` generates the matching Liquibase `<createIndex>`/`<dropIndex>` changeset (using the same `IDX_{TABLE}_UNQ_{FIELD}` index name as the base changelog) and synchronizes the Java `@Table(indexes = ...)` annotation — adding `@Index` entries with correct comma separation and `import jakarta.persistence.Index;`, or removing them and cleaning up empty `indexes` arrays.
- Dropped columns are destructive; the command prompts before writing the Liquibase change and before removing the field from the Java entity

### ui-list-all / ui-detail-all with User entity

```bash
# Generate/update ALL list views
python3 jmix-cli.py ui-list-all

# Generate/update ALL detail views
python3 jmix-cli.py ui-detail-all
```

For the built-in `User` entity, `ui-list-all` and `ui-detail-all` do **not** regenerate views from `entities.csv` (which would overwrite standard User fields). Instead, they:
- **Inject new fields** from `entities.csv` as columns (`user-list-view.xml`) or form components (`user-detail-view.xml`) into the existing views
- **Inject new relations** from `relations.csv` into the existing views
- **Remove dropped fields** that are no longer in `entities.csv` (excluding standard User fields)

This ensures that standard User fields (username, firstName, lastName, email, active, timeZoneId) are preserved in the views while custom fields are kept in sync with `entities.csv`.

### Dry-Run Mode

```bash
# Test generation in a temp project without touching the current one
python3 jmix-cli.py --dry-run build-all
python3 jmix-cli.py --dry-run entity-all
python3 jmix-cli.py --dry-run entity Project
```

Compatible with all generation commands except `init`:
- `--dry-run build-all`
- `--dry-run entity-all`
- `--dry-run entity <Name>`
- `--dry-run ui-detail-all`
- `--dry-run ui-detail <Name>`
- `--dry-run ui-list-all`
- `--dry-run ui-list <Name>`
- `--dry-run security`

Benefits:
- Copies the current project into a temp directory and runs generation there
- Sets `server.port=0` so the temporary app won't conflict with a running instance
- Prints a summary with generated file counts and a suggested `meld` diff command
- Great for validating CSV changes before applying them to the real project
- Does not support `init`, because initialization is already a clean/new-project operation

## Security Roles

| Role | Code | Permissions |
|------|------|-------------|
| **Project Manager** | project-manager | Full access to Project, Milestone, Team, Client; Read-only for Task (assigned), TaskComment, Priority |
| **Developer** | developer-role | Full access to Task, TaskComment; Read-only for Milestone, Priority; No User access |
| **Client Viewer** | client-viewer | Read-only access to Project, Task |

## Running the Application

```bash
# Clone the project in your computer
git clone https://github.com/florintanasa/agilepm
# Full generation (all phases)
python3 jmix-cli.py build-all
# Run application
./gradlew bootRun
# Access at http://localhost:8080 with admin/admin credentials
```

## Only to compile

```bash
./gradlew compileJava
```

## To clean your build

```bash
./gradlew clean
```

## Testing

```bash
./gradlew test
```

> [!WARNING]  
> If you have errors caused by Liquibase `liquibase.exception.DatabaseException: object name already exists: ` these mean you have an old database,
> and is necessary to delete the old files: `rm -rf .jmix/ build/ .gradle/`

## Demo data
In `listener` exist a class `AgileDemoDataIniTializer` this populate the data base with values at first run.  
To test the users roles we can use next credentials:
|User|Password|Roles|
|----|--------|-----|
|`manager`|1|ui-minimal, project-manager|
|`developer`|1|ui-minimal, developer-role|
|`client`|1|ui-minimal, client-viewer|

## CSV Configuration Tables

### traits.csv - Entity Traits Configuration

| entity_name | versioned | audit_of_creation | audit_of_modification | soft_delete |
|-------------|-----------|-----------------|---------------------|-------------|
| Project | true | true | true | true |
| Milestone | true | true | true | false |
| Task | true | true | true | true |
| TaskComment | true | true | false | false |
| Priority | true | false | false | false |
| UserProfile | true | true | true | false |
| UserConfig | true | false | false | false |
| Team | true | true | true | false |
| Client | true | true | true | true |

### entities.csv - Entity Attributes Configuration

| entity_name | field_name | field_type | mandatory | unique |
|-------------|------------|------------|-----------|--------|
| Project | name | String | true | true |
| Project | startDate | LocalDate | true | false |
| Milestone | title | String | true | false |
| Milestone | targetDate | LocalDate | false | false |
| Task | subject | String | true | false |
| Task | dueDate | LocalDate | true | false |
| TaskComment | content | String | true | false |
| Priority | level | String | true | true |
| UserProfile | phoneNumber | String | false | false |
| UserConfig | theme | String | true | false |
| Team | name | String | true | true |
| Client | companyName | String | true | true |

### relations.csv - Entity Relationships Configuration

| source_entity | relation_type | target_entity | field_name | mandatory | ownership |
|---------------|-------------|---------------|------------|-----------|-----------|
| Milestone | COMPOSITION_1:N | Project | milestones | true |  |
| Milestone | N:1 | Project | project | true |  |
| Task | N:1 | Milestone | milestone | false |  |
| TaskComment | COMPOSITION_1:N | Task | comments | false |  |
| TaskComment | N:1 | Task | task | true |  |
| Task | N:1 | User | assignee | false |  |
| Task | N:1 | Priority | priority | true |  |
| TaskComment | N:1 | User | author | true |  |
| User | N:1 | Team | team | false |  |
| User | N:N | Priority | priorities | false | owning |
| User | 1:1 | UserProfile | profile | false |  |
| UserProfile | 1:1 | User | user | true |  |
| UserConfig | COMPOSITION_1:1 | UserProfile | profile | true |  |
| Team | N:N | Client | clients | false | both-owning |

### roles.csv - Security Roles Configuration

| name | code | entity_name | ui_list | ui_detail | create | read | update | delete |
|------|------|-------------|---------|-----------|--------|------|--------|--------|
| Project Manager | project-manager | Project | true | true | true | true | true | true |
| Project Manager | project-manager | Milestone | true | true | true | true | true | true |
| Project Manager | project-manager | Team | true | true | true | true | true | true |
| Project Manager | project-manager | Client | true | true | true | true | true | true |
| Project Manager | project-manager | Task | true | true | false | true | false | false |
| Project Manager | project-manager | TaskComment | true | false | false | true | false | false |
| Project Manager | project-manager | Priority | false | false | false | true | false | false |
| Developer Role | developer-role | Task | true | true | true | true | true | true |
| Developer Role | developer-role | TaskComment | true | true | true | true | true | true |
| Developer Role | developer-role | Milestone | true | false | false | true | false | false |
| Developer Role | developer-role | Priority | false | false | false | true | false | false |
| Developer Role | developer-role | User | false | false | false | true | false | false |
| Client Viewer | client-viewer | Project | true | false | false | true | false | false |
| Client Viewer | client-viewer | Task | true | false | false | true | false | false |

## Screenshoot
![ Agile Project Management System](agilepm_screenshoot.png)
