let patients = [];
let ressourcesData = {};
const besoins_par_esi = {
    1: ['lit_rea', 'moniteur', 'medicament_urgence'],
    2: ['suture', 'poche_sang', 'scanner'],
    3: ['ecg', 'medicament_urgence', 'radio_x'],
    4: ['radio_x', 'poche_sang', 'labo_analyses'],
    5: ['suture', 'scanner', 'labo_analyses']
};

function ajouterPatient() {
    const id = document.getElementById('id').value;
    const esi = parseInt(document.getElementById('esi').value);
    const fenetre = parseFloat(document.getElementById('fenetre').value);
    const gravite = Math.floor(Math.random() * (11 - esi)) + (11 - esi);
    const score_priorite = (gravite / fenetre).toFixed(2);
    const besoins = besoins_par_esi[esi].slice();
    if (esi === 1 && Math.random() < 0.3) {
        besoins.push(Math.random() < 0.5 ? 'irm' : 'respirateur');
    }

    patients.push({
        id: id,
        esi: esi,
        fenetre: fenetre,
        gravite: gravite,
        score_priorite: score_priorite,
        besoins: besoins,
        assignation_initiale: null,
        hopital: '-'
    });

    updatePatientsTable();
    document.getElementById('patientForm').reset();
}

function updatePatientsTable() {
    const tbody = document.getElementById('patientsTable');
    tbody.innerHTML = '';
    patients.forEach(p => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${p.id}</td>
            <td>${p.esi}</td>
            <td>${p.fenetre}</td>
            <td>${p.besoins.join(', ')}</td>
            <td><span class="badge ${p.hopital === 'A' ? 'bg-primary' : p.hopital === '-' ? 'bg-secondary' : p.hopital === 'Non assigné' ? 'bg-danger' : 'bg-info'}">${p.hopital}</span></td>
        `;
        tbody.appendChild(row);
    });
}

function updateRessourcesTable() {
    const tbody = document.getElementById('ressourcesTable');
    tbody.innerHTML = '';
    for (const [hopital, res] of Object.entries(ressourcesData)) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${hopital}</td>
            <td>${Object.entries(res).map(([k, v]) => `${k}: ${v}`).join(', ')}</td>
        `;
        tbody.appendChild(row);
    }
}

function evaluerModele() {
    fetch('/evaluer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patients: patients })
    })
    .then(response => response.json())
    .then(data => {
        Object.keys(data.affectations).forEach(id => {
            const patient = patients.find(p => p.id === id);
            if (patient) {
                patient.hopital = data.affectations[id].hopital + (data.affectations[id].temps_transfert > 0 ? ` (${data.affectations[id].temps_transfert.toFixed(2)}h)` : '');
            }
        });
        updatePatientsTable();

        ressourcesData = data.ressources_restantes;
        console.log("Ressources reçues :", ressourcesData);  // Débogage
        updateRessourcesTable();  // Mettre à jour le tableau

        const ctx = document.getElementById('resultChart').getContext('2d');
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Assignation', 'Priorités ESI 1', 'Ressources', 'Transferts'],
                datasets: [{
                    label: 'Performance (%)',
                    data: [data.taux_assignation, data.taux_esi_1, data.taux_ressources, data.taux_transferts],
                    backgroundColor: ['#4CAF50', '#2196F3', '#FFC107', '#FF5722']
                }]
            },
            options: {
                scales: { y: { beginAtZero: true, max: 100 } },
                plugins: { legend: { display: false } }
            }
        });
    })
    .catch(error => console.error("Erreur lors de l'évaluation :", error));
}

function reinitialiser() {
    patients = [];
    ressourcesData = {};
    updatePatientsTable();
    updateRessourcesTable();  // Réinitialiser le tableau des ressources
    document.getElementById('resultChart').getContext('2d').clearRect(0, 0, document.getElementById('resultChart').width, document.getElementById('resultChart').height);
}