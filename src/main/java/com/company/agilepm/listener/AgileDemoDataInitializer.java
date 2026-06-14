package com.company.agilepm.listener;

import com.company.agilepm.entity.*;
import io.jmix.core.DataManager;
import io.jmix.core.security.Authenticated;
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
		// Verificăm dacă baza de date conține deja priorități de test (evită duplicarea datelor)
		if (!dm.load(Priority.class).all().maxResults(1).list().isEmpty()) {
			return;
		}

		System.out.println(
			"🚀 [Seeding] Începe popularea automată cu date pentru ecosistemul AgilePM..."
		);

		// 1. Populăm prioritățile (Nomenclator independent)
		Priority pLow = createPriority("Low");
		Priority pMedium = createPriority("Medium");
		Priority pHigh = createPriority("High");

		// 2. Populăm clienții și echipele de dezvoltare
		Client clientAlfa = createClient("Alfa Software SRL");
		Client clientBeta = createClient("Beta Enterprise Corp");

		Team teamAlpha = createTeam("Echipa Alpha (Backend)");
		Team teamDelta = createTeam("Echipa Delta (FlowUI)");

		// 3. Creăm utilizatori de sistem Jmix și îi alocăm în echipe (Infiltrare)
		User employee = dm.create(User.class);
		employee.setUsername("developer");
		employee.setPassword(encoder.encode("1"));
		employee.setFirstName("John");
		employee.setLastName("Doe");
		employee.setTeam(teamAlpha); // Alocare în echipă
		dm.save(employee);

		// 4. Creăm un proiect principal și etapele sale de business (Milestones)
		Project projectCRM = dm.create(Project.class);
		projectCRM.setName("Sistem Core CRM Modernization");
		projectCRM.setStartDate(LocalDate.now());
		dm.save(projectCRM);

		Milestone m1 = createMilestone(
			"Arhitectura de Bază & CLI",
			LocalDate.now().plusDays(10),
			projectCRM
		);
		Milestone m2 = createMilestone(
			"Interfața Grafică FlowUI",
			LocalDate.now().plusDays(30),
			projectCRM
		);

		// 5. Generăm task-uri de lucru legate de etape, priorități și utilizatori
		Task task1 = dm.create(Task.class);
		task1.setSubject("Implementare sortare topologică în generator");
		task1.setDueDate(LocalDate.now().plusDays(5));
		task1.setPriority(pHigh);
		task1.setMilestone(m1);
		task1.setAssignee(employee);
		dm.save(task1);

		Task task2 = dm.create(Task.class);
		task2.setSubject("Configurare ecrane de detalii pentru compoziții");
		task2.setDueDate(LocalDate.now().plusDays(15));
		task2.setPriority(pMedium);
		task2.setMilestone(m2);
		task2.setAssignee(employee);
		dm.save(task2);

		// 6. Adăugăm comentarii de test atașate sarcinilor de lucru (Compoziție)
		createComment(
			"Algoritmul topological funcționează perfect fără recursivitate.",
			employee,
			task1
		);
		createComment(
			"Trebuie verificată corelația atributului mappedBy în clasa părinte.",
			employee,
			task1
		);

		System.out.println(
			"✨ [Seeding] Toate cele 10 entități ierarhice au primit date inițiale de producție!"
		);
	}

	// Metode helper pentru a păstra execuția compactă și lizibilă
	private Priority createPriority(String level) {
		Priority p = dm.create(Priority.class);
		p.setLevel(level);
		return dm.save(p);
	}

	private Client createClient(String name) {
		Client c = dm.create(Client.class);
		c.setCompanyName(name);
		return dm.save(c);
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
		m.setProject(p); // Legătură compoziție părinte
		return dm.save(m);
	}

	private void createComment(String content, User author, Task task) {
		TaskComment tc = dm.create(TaskComment.class);
		tc.setContent(content);
		tc.setAuthor(author);
		tc.setTask(task); // Legătură compoziție părinte task
		dm.save(tc);
	}
}
