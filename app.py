from flask import Flask, render_template, request, jsonify
import pickle
import random
from copy import deepcopy

app = Flask(__name__)

# Charger le modèle initial
with open('modele_hopital.pkl', 'rb') as f:
    donnees = pickle.load(f)
patients_init = donnees['patients_test']
hopitaux_init = donnees['hopitaux_sim']
assignations_init = donnees['assignations_temps']
transferes_init = donnees['transferes']

DUREES_OCCUPATION = {
    'lit_rea': 4, 'moniteur': 2, 'respirateur': 2, 'scanner': 1, 'ecg': 0.5, 'suture': 0.5, 
    'labo_analyses': 1, 'irm': 1, 'radio_x': 0.5, 'poche_sang': 0.5, 'medicament_urgence': 0.25
}

def assigner_ressources_localement(patients, hopital, assignations_temps, hopital_name):
    assignes = []
    non_assignes = []
    # Trier par ESI pour prioriser les urgences (ESI 1 en premier)
    patients = sorted(patients, key=lambda p: p['esi'])
    for patient in patients:
        toutes_ressources_dispo = all(
            ressource in hopital['ressources'] and hopital['ressources'][ressource] > 0 
            for ressource in patient['besoins']
        )
        if toutes_ressources_dispo and patient['assignation_initiale'] == hopital_name:
            assignes.append(patient)
            for ressource in patient['besoins']:
                hopital['ressources'][ressource] -= 1
                assignations_temps.append({
                    'patient': patient['id'], 
                    'ressource': ressource, 
                    'duree': DUREES_OCCUPATION[ressource], 
                    'temps_restant': DUREES_OCCUPATION[ressource], 
                    'hopital': hopital_name
                })
        else:
            non_assignes.append(patient)
    return assignes, non_assignes

def gerer_transferts(non_assignes, hopitaux, hopital_local='A', assignations_temps=None):
    transferes = {}
    patients_toujours_non_assignes = []
    # Trier par ESI pour prioriser les urgences
    non_assignes = sorted(non_assignes, key=lambda p: p['esi'])
    for patient in non_assignes:
        options_transfert = []
        for h_name, h_data in hopitaux.items():
            if h_name != hopital_local:
                temps_transport = hopitaux[h_name]['distances']['A'] / 60
                # Vérifier que le temps de transfert est strictement inférieur à la fenêtre
                if temps_transport < patient['fenetre']:
                    toutes_ressources_dispo = all(
                        ressource in h_data['ressources'] and h_data['ressources'][ressource] > 0 
                        for ressource in patient['besoins']
                    )
                    if toutes_ressources_dispo:
                        reserve = sum(h_data['ressources'][ressource] for ressource in patient['besoins'] if ressource in h_data['ressources'])
                        options_transfert.append((h_name, temps_transport, reserve))
        if options_transfert:
            # Choisir l’hôpital avec le meilleur temps de transfert et le plus de ressources
            meilleur_hopital = sorted(options_transfert, key=lambda x: (x[1], -x[2]))[0]
            h_name, temps_transport, _ = meilleur_hopital
            transferes[patient['id']] = {'hopital': h_name, 'temps_transfert': temps_transport}
            for ressource in patient['besoins']:
                hopitaux[h_name]['ressources'][ressource] -= 1
                if assignations_temps is not None:
                    assignations_temps.append({
                        'patient': patient['id'], 
                        'ressource': ressource, 
                        'duree': DUREES_OCCUPATION[ressource], 
                        'temps_restant': DUREES_OCCUPATION[ressource], 
                        'hopital': h_name
                    })
        else:
            patients_toujours_non_assignes.append(patient)
    return transferes, patients_toujours_non_assignes

def simuler_temps(assignations_temps, hopitaux, delta_temps=1):
    for assignation in assignations_temps[:]:
        assignation['temps_restant'] -= delta_temps
        if assignation['temps_restant'] <= 0:
            hopitaux[assignation['hopital']]['ressources'][assignation['ressource']] += 1
            assignations_temps.remove(assignation)

def evaluer_modele(patients, hopitaux, assignations_temps, transferes):
    total_patients = len(patients)
    assignes_reussis = 0
    esi_1_reussis = 0
    ressources_adéquates = 0
    transferts_valides = 0
    total_esi_1 = sum(1 for p in patients if p['esi'] == 1)
    total_transferes = sum(1 for p in patients if p['assignation_initiale'] is None)
    affectations = {}

    for patient in patients:
        hopital = patient['assignation_initiale'] if patient['assignation_initiale'] else transferes.get(patient['id'], {}).get('hopital', None)
        temps_transfert = transferes.get(patient['id'], {}).get('temps_transfert', 0)
        affectations[patient['id']] = {'hopital': hopital if hopital else 'Non assigné', 'temps_transfert': temps_transfert}

        if hopital and hopital != 'Non assigné':
            assignes_reussis += 1
            toutes_ressources_dispo = all(
                ressource in hopitaux[hopital]['ressources'] and hopitaux[hopital]['ressources'][ressource] >= 0
                for ressource in patient['besoins']
            )
            if toutes_ressources_dispo:
                ressources_adéquates += 1
        if patient['esi'] == 1 and hopital and hopital != 'Non assigné' and (temps_transfert == 0 or temps_transfert <= patient['fenetre']):
            esi_1_reussis += 1
        if patient['id'] in transferes and temps_transfert <= patient['fenetre']:
            transferts_valides += 1

    ressources_restantes = {h: hopitaux[h]['ressources'] for h in hopitaux}

    return {
        'taux_assignation': (assignes_reussis / total_patients) * 100,
        'taux_esi_1': (esi_1_reussis / total_esi_1) * 100 if total_esi_1 > 0 else 100,
        'taux_ressources': (ressources_adéquates / total_patients) * 100,
        'taux_transferts': (transferts_valides / total_transferes) * 100 if total_transferes > 0 else 100,
        'total_patients': total_patients,
        'assignes_reussis': assignes_reussis,
        'esi_1_reussis': esi_1_reussis,
        'ressources_adéquates': ressources_adéquates,
        'transferts_valides': transferts_valides,
        'total_esi_1': total_esi_1,
        'total_transferes': total_transferes,
        'affectations': affectations,
        'ressources_restantes': ressources_restantes
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/evaluer', methods=['POST'])
def evaluer():
    data = request.json
    patients = data.get('patients', [])
    # Ajuster les fenêtres temporelles pour éviter 0
    for patient in patients:
        if patient['fenetre'] < 0.1:
            patient['fenetre'] = 0.1  # Fenêtre minimale de 0.1h
    hopitaux_sim = deepcopy(hopitaux_init)
    assignations_temps = []
    
    patients_assignes, patients_non_assignes = assigner_ressources_localement(patients, hopitaux_sim['A'], assignations_temps, 'A')
    transferes, non_assignes = gerer_transferts(patients_non_assignes, hopitaux_sim, 'A', assignations_temps)
    simuler_temps(assignations_temps, hopitaux_sim, delta_temps=1)
    resultats = evaluer_modele(patients, hopitaux_sim, assignations_temps, transferes)
    
    return jsonify(resultats)

if __name__ == '__main__':
    app.run(debug=True)