package com.company.agilepm.listener;

import com.company.agilepm.entity.*;
import io.jmix.core.DataManager;
import io.jmix.core.security.Authenticated;
import io.jmix.security.role.assignment.RoleAssignmentRoleType;
import io.jmix.securitydata.entity.RoleAssignmentEntity;
import java.time.LocalDate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.event.ApplicationStartedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

@Component
public class AgileDemoDataInitializer {

	@Autowired
	private DataManager dm;

	@Autowired
	private PasswordEncoder encoder;

	@EventListener
	@Authenticated
	public void onApplicationStarted(ApplicationStartedEvent event) {
		// Safety check to bypass duplication if test data already exists
		if (!dm.load(Priority.class).all().maxResults(1).list().isEmpty()) {
			return;
		}

		System.out.println(
			"🚀 [Seeding] Launching global data initialization sequence for AgilePM ecosystem..."
		);

		// 1. Initialize Lookups (Executed cleanly)
		Priority pMedium = createPriority("Medium");
		Priority pHigh = createPriority("High");

		createPriority("Low");
		createClient("Alfa Software SRL");
		createClient("Beta Enterprise Corp");

		Team teamAlpha = createTeam("Alpha Backend Squad");
		Team teamDelta = createTeam("Delta FlowUI Engineers");

		// 2. Instantiate and Seed Users for Specific Custom Roles
		User managerUser = dm.create(User.class);
		managerUser.setUsername("manager");
		managerUser.setPassword(encoder.encode("1"));
		managerUser.setFirstName("Robert");
		managerUser.setLastName("Taylor");
		managerUser.setTeam(teamAlpha);
		dm.save(managerUser);
		assignRoleToUser(managerUser.getUsername(), "ui-minimal");
		assignRoleToUser(managerUser.getUsername(), "project-manager");

		User developerUser = dm.create(User.class);
		developerUser.setUsername("developer");
		developerUser.setPassword(encoder.encode("1"));
		developerUser.setFirstName("John");
		developerUser.setLastName("Doe");
		developerUser.setTeam(teamAlpha);
		dm.save(developerUser);
		assignRoleToUser(developerUser.getUsername(), "ui-minimal");
		assignRoleToUser(developerUser.getUsername(), "developer-role");

		User clientUser = dm.create(User.class);
		clientUser.setUsername("client");
		clientUser.setPassword(encoder.encode("1"));
		clientUser.setFirstName("Alice");
		clientUser.setLastName("Brown");
		clientUser.setTeam(teamDelta);
		dm.save(clientUser);
		assignRoleToUser(clientUser.getUsername(), "ui-minimal");
		assignRoleToUser(clientUser.getUsername(), "client-viewer");

		// 3. Populate UserConfig & UserProfile (1:1 Relation)
		UserProfile devProfile = dm.create(UserProfile.class);
		devProfile.setPhoneNumber("+40712345678");
		devProfile.setUser(developerUser);
		devProfile = dm.save(devProfile);

		UserConfig devConfig = dm.create(UserConfig.class);
		devConfig.setTheme("Dark-Mode-Zed");
		devConfig.setProfile(devProfile);
		dm.save(devConfig);

		UserProfile mgrProfile = dm.create(UserProfile.class);
		mgrProfile.setPhoneNumber("+40799988877");
		mgrProfile.setUser(managerUser);
		mgrProfile = dm.save(mgrProfile);

		UserConfig mgrConfig = dm.create(UserConfig.class);
		mgrConfig.setTheme("Light-Mode-Standard");
		mgrConfig.setProfile(mgrProfile);
		dm.save(mgrConfig);

		// 4. Populate Operational Data Structures & Compositions
		Project projectCRM = dm.create(Project.class);
		projectCRM.setName("Sistem Core CRM Modernization");
		projectCRM.setStartDate(LocalDate.now());
		dm.save(projectCRM);

		// FIX: Stocăm instanțele etapelor pentru a le folosi la Task-uri
		Milestone m1 = createMilestone(
			"Core Architecture & CLI Design",
			LocalDate.now().plusDays(10),
			projectCRM
		);
		Milestone m2 = createMilestone(
			"FlowUI Nested Form Presentation Layer",
			LocalDate.now().plusDays(30),
			projectCRM
		);

		// 5. Anchor Tasks Linked to Users, Priorities, and Milestones
		Task task1 = dm.create(Task.class);
		task1.setSubject("Resolve recursive camelCase generation string bugs");
		task1.setDueDate(LocalDate.now().plusDays(5));
		task1.setPriority(pHigh);
		task1.setMilestone(m1);
		task1.setAssignee(developerUser);
		dm.save(task1);

		Task task2 = dm.create(Task.class);
		task2.setSubject(
			"Infiltrate custom collection dataGrid tables inside User detail layout"
		);
		task2.setDueDate(LocalDate.now().plusDays(15));
		task2.setPriority(pMedium);
		task2.setMilestone(m2);
		task2.setAssignee(developerUser);
		dm.save(task2);

		// 6. Append Embedded Composition Elements (Task Comments Hierarchy)
		createComment(
			"Topological execution pipeline works perfectly without loops.",
			developerUser,
			task1
		);
		createComment(
			"Verified mappedBy metadata sync parameters inside parent tracking layout.",
			managerUser,
			task1
		);

		System.out.println(
			"✨ [Seeding] Structural data initialization completed successfully across all 10 modules!"
		);
	}

	// Programmatic Role Assignment Engine Helper
	private void assignRoleToUser(String username, String roleCode) {
		RoleAssignmentEntity assignment = dm.create(RoleAssignmentEntity.class);
		assignment.setUsername(username);
		assignment.setRoleCode(roleCode);
		assignment.setRoleType(RoleAssignmentRoleType.RESOURCE);
		dm.save(assignment);
	}

	// Structural Helper Factory Methods
	private Priority createPriority(String level) {
		Priority p = dm.create(Priority.class);
		p.setLevel(level);
		return dm.save(p);
	}

	private void createClient(String name) {
		Client c = dm.create(Client.class);
		c.setCompanyName(name);
		dm.save(c);
	}

	private Team createTeam(String name) {
		Team t = dm.create(Team.class);
		t.setName(name);
		return dm.save(t);
	}

	private Milestone createMilestone(
		String title,
		LocalDate target,
		Project p
	) {
		Milestone m = dm.create(Milestone.class);
		m.setTitle(title);
		m.setTargetDate(target);
		m.setProject(p);
		return dm.save(m);
	}

	private void createComment(String content, User author, Task task) {
		TaskComment tc = dm.create(TaskComment.class);
		tc.setContent(content);
		tc.setAuthor(author);
		tc.setTask(task);
		dm.save(tc);
	}
}
