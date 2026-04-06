"""Built-in Java Developer skill.

Provides Java/Spring Boot-specific tools for project scaffolding,
Maven/Gradle builds, class generation, and Spring integration helpers.
"""
from __future__ import annotations

from typing import Any

from manch_backend.models import RiskLevel
from manch_backend.skills import BaseSkill, SkillKind, SkillManifest


class JavaDeveloperSkill(BaseSkill):
    manifest = SkillManifest(
        name="java-developer",
        version="1.0.0",
        description=(
            "Java & Spring Boot development tools — Maven/Gradle builds, class/interface "
            "scaffolding, Spring Boot starters, JUnit test generation, and dependency management."
        ),
        kind=SkillKind.TOOL,
        risk_level=RiskLevel.MEDIUM,
        author="Manch",
        tags=["builtin", "java", "spring-boot", "backend", "maven", "gradle"],
        dependencies=["sandbox-tools"],
        config_schema={
            "java_version": {"type": "string", "default": "21", "description": "Target Java LTS version"},
            "build_tool": {"type": "string", "default": "maven", "description": "maven or gradle"},
            "spring_boot_version": {"type": "string", "default": "3.3", "description": "Spring Boot version"},
        },
    )

    def register(self) -> None:
        from manch_backend.agents.tools import ToolSpec, register_tool, get_tool

        tools = [
            ToolSpec(
                name="java_build",
                description=(
                    "Run Maven or Gradle build. Defaults to 'mvn clean package -DskipTests'. "
                    "Pass a custom command if needed."
                ),
                risk_level=RiskLevel.MEDIUM,
                handler=self._build,
            ),
            ToolSpec(
                name="java_test",
                description="Run Java unit tests via Maven Surefire or Gradle test.",
                risk_level=RiskLevel.MEDIUM,
                handler=self._test,
            ),
            ToolSpec(
                name="java_generate_class",
                description=(
                    "Scaffold a Java class file with package declaration, imports, and "
                    "boilerplate. Provide fully-qualified class name and type (class/interface/enum/record)."
                ),
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_class,
            ),
            ToolSpec(
                name="java_generate_spring_controller",
                description="Scaffold a Spring Boot REST controller with common CRUD endpoints.",
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_controller,
            ),
            ToolSpec(
                name="java_generate_spring_service",
                description="Scaffold a Spring Boot @Service class with @Transactional support.",
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_service,
            ),
            ToolSpec(
                name="java_generate_jpa_entity",
                description="Scaffold a JPA @Entity class with @Id, @GeneratedValue, and field mappings.",
                risk_level=RiskLevel.MEDIUM,
                handler=self._generate_entity,
            ),
            ToolSpec(
                name="java_dependency_add",
                description=(
                    "Add a Maven dependency to pom.xml. Provide groupId, artifactId, "
                    "and optional version."
                ),
                risk_level=RiskLevel.MEDIUM,
                handler=self._add_dependency,
            ),
            ToolSpec(
                name="java_checkstyle",
                description="Run Checkstyle or SpotBugs analysis on the Java project.",
                risk_level=RiskLevel.LOW,
                handler=self._checkstyle,
            ),
        ]

        for spec in tools:
            if not get_tool(spec.name):
                register_tool(spec)

    # ── Tool handlers ────────────────────────────────

    @staticmethod
    def _build(sandbox_session_id: str, command: str = "", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        cmd = command or "mvn clean package -DskipTests -q 2>&1 | tail -30"
        return _run_sandbox_command(sandbox_session_id, f"cd /workspace && {cmd}")

    @staticmethod
    def _test(sandbox_session_id: str, command: str = "", **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        cmd = command or "mvn test 2>&1 | tail -50"
        return _run_sandbox_command(sandbox_session_id, f"cd /workspace && {cmd}")

    @staticmethod
    def _generate_class(
        sandbox_session_id: str,
        fqn: str,
        class_type: str = "class",
        **_: Any,
    ):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file
        parts = fqn.rsplit(".", 1)
        package = parts[0] if len(parts) > 1 else "com.example"
        class_name = parts[-1]
        path_prefix = "src/main/java/" + package.replace(".", "/")

        content = f"package {package};\n\npublic {class_type} {class_name} {{\n\n}}\n"

        _run_sandbox_command(sandbox_session_id, f"mkdir -p /workspace/{path_prefix}")
        return _write_file(sandbox_session_id, f"{path_prefix}/{class_name}.java", content)

    @staticmethod
    def _generate_controller(
        sandbox_session_id: str,
        entity_name: str,
        package: str = "com.example.controller",
        **_: Any,
    ):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file
        path_prefix = "src/main/java/" + package.replace(".", "/")

        content = f"""package {package};

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import java.util.List;

@RestController
@RequestMapping("/api/{entity_name.lower()}s")
public class {entity_name}Controller {{

    // TODO: Inject {entity_name}Service

    @GetMapping
    public ResponseEntity<List<Object>> findAll() {{
        return ResponseEntity.ok(List.of());
    }}

    @GetMapping("/{{id}}")
    public ResponseEntity<Object> findById(@PathVariable Long id) {{
        return ResponseEntity.ok(null);
    }}

    @PostMapping
    public ResponseEntity<Object> create(@RequestBody Object body) {{
        return ResponseEntity.status(201).body(body);
    }}

    @PutMapping("/{{id}}")
    public ResponseEntity<Object> update(@PathVariable Long id, @RequestBody Object body) {{
        return ResponseEntity.ok(body);
    }}

    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {{
        return ResponseEntity.noContent().build();
    }}
}}
"""
        _run_sandbox_command(sandbox_session_id, f"mkdir -p /workspace/{path_prefix}")
        return _write_file(sandbox_session_id, f"{path_prefix}/{entity_name}Controller.java", content)

    @staticmethod
    def _generate_service(
        sandbox_session_id: str,
        entity_name: str,
        package: str = "com.example.service",
        **_: Any,
    ):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file
        path_prefix = "src/main/java/" + package.replace(".", "/")

        content = f"""package {package};

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.Optional;

@Service
@Transactional
public class {entity_name}Service {{

    public List<Object> findAll() {{
        return List.of();
    }}

    public Optional<Object> findById(Long id) {{
        return Optional.empty();
    }}

    public Object create(Object entity) {{
        return entity;
    }}

    public Object update(Long id, Object entity) {{
        return entity;
    }}

    public void delete(Long id) {{
        // TODO: implement
    }}
}}
"""
        _run_sandbox_command(sandbox_session_id, f"mkdir -p /workspace/{path_prefix}")
        return _write_file(sandbox_session_id, f"{path_prefix}/{entity_name}Service.java", content)

    @staticmethod
    def _generate_entity(
        sandbox_session_id: str,
        entity_name: str,
        package: str = "com.example.entity",
        fields: str = "",
        **_: Any,
    ):
        from manch_backend.agents.tools import _run_sandbox_command, _write_file
        path_prefix = "src/main/java/" + package.replace(".", "/")

        field_lines = ""
        if fields:
            for f in fields.split(","):
                f = f.strip()
                parts = f.split(":")
                if len(parts) == 2:
                    field_lines += f"\n    @Column\n    private {parts[0].strip()} {parts[1].strip()};\n"

        content = f"""package {package};

import jakarta.persistence.*;

@Entity
@Table(name = "{entity_name.lower()}s")
public class {entity_name} {{

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
{field_lines}
    // Getters and setters

    public Long getId() {{ return id; }}
    public void setId(Long id) {{ this.id = id; }}
}}
"""
        _run_sandbox_command(sandbox_session_id, f"mkdir -p /workspace/{path_prefix}")
        return _write_file(sandbox_session_id, f"{path_prefix}/{entity_name}.java", content)

    @staticmethod
    def _add_dependency(
        sandbox_session_id: str,
        group_id: str,
        artifact_id: str,
        version: str = "",
        **_: Any,
    ):
        from manch_backend.agents.tools import _run_sandbox_command
        import shlex
        version_tag = f"\n            <version>{version}</version>" if version else ""
        dep_xml = f"""        <dependency>
            <groupId>{group_id}</groupId>
            <artifactId>{artifact_id}</artifactId>{version_tag}
        </dependency>"""
        safe = shlex.quote(dep_xml)
        return _run_sandbox_command(
            sandbox_session_id,
            f"cd /workspace && sed -i '/<\\/dependencies>/i\\{safe}' pom.xml 2>&1 "
            f"&& echo 'Added dependency {group_id}:{artifact_id}'",
        )

    @staticmethod
    def _checkstyle(sandbox_session_id: str, **_: Any):
        from manch_backend.agents.tools import _run_sandbox_command
        return _run_sandbox_command(
            sandbox_session_id,
            "cd /workspace && mvn checkstyle:check 2>&1 | tail -40 || "
            "echo 'Checkstyle plugin not configured. Add maven-checkstyle-plugin to pom.xml.'",
        )


# Module-level instance for auto-discovery
skill = JavaDeveloperSkill()
