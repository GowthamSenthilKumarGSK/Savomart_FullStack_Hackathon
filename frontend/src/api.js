import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export async function fetchPincodeBoundaries() {
  const { data } = await api.get('/pincodes/boundaries')
  return data
}

export async function fetchPincodeDetail(pincode) {
  const { data } = await api.get(`/pincodes/${pincode}`)
  return data
}

export async function fetchStores() {
  const { data } = await api.get('/stores')
  return data
}

export async function fetchFitnessReport(pincode) {
  const { data } = await api.get(`/pincodes/${pincode}/fitness`)
  return data
}

export async function fetchHotspots(pincode) {
  const { data } = await api.get(`/pincodes/${pincode}/hotspots`)
  return data
}

export async function fetchExplanation(pincode, reportId) {
  const { data } = await api.post(`/pincodes/${pincode}/fitness/${reportId}/explain`)
  return data
}

export async function fetchFitnessHistory(pincode) {
  const { data } = await api.get(`/pincodes/${pincode}/fitness/history`)
  return data
}

export async function fetchSavedReport(pincode, reportId) {
  const { data } = await api.get(`/pincodes/${pincode}/fitness/${reportId}`)
  return data
}

export async function createScoutingTask(payload) {
  const { data } = await api.post('/scouting-tasks', payload)
  return data
}

export async function fetchScoutingTasks(params = {}) {
  const { data } = await api.get('/scouting-tasks', { params })
  return data
}

export async function fetchScoutingTask(taskId) {
  const { data } = await api.get(`/scouting-tasks/${taskId}`)
  return data
}

export async function updateScoutingTask(taskId, payload) {
  const { data } = await api.patch(`/scouting-tasks/${taskId}`, payload)
  return data
}

export async function submitProperty(taskId, payload) {
  const { data } = await api.post(`/scouting-tasks/${taskId}/property`, payload)
  return data
}

export async function getEvaluation(propertyId) {
  const { data } = await api.get(`/properties/${propertyId}/evaluation`)
  return data
}

export async function runEvaluation(propertyId) {
  const { data } = await api.post(`/properties/${propertyId}/evaluate`)
  return data
}

export async function requestCatchmentStudy(payload) {
  const { data } = await api.post('/catchment-studies', payload)
  return data
}

export async function fetchCatchmentStudies(params = {}) {
  const { data } = await api.get('/catchment-studies', { params })
  return data
}

export async function fetchCatchmentStudy(studyId) {
  const { data } = await api.get(`/catchment-studies/${studyId}`)
  return data
}

export async function createZoneAssignment(studyId, payload) {
  const { data } = await api.post(`/catchment-studies/${studyId}/assignments`, payload)
  return data
}

export async function updateAssignmentStatus(assignmentId, payload) {
  const { data } = await api.patch(`/catchment-studies/assignments/${assignmentId}/status`, payload)
  return data
}

export async function fetchAssignmentRoads(assignmentId) {
  const { data } = await api.get(`/catchment-studies/assignments/${assignmentId}/roads`)
  return data
}

export async function fetchAssignmentSurveys(assignmentId) {
  const { data } = await api.get(`/catchment-studies/assignments/${assignmentId}/surveys`)
  return data
}

export async function submitLaneSurvey(assignmentId, payload) {
  const { data } = await api.post(`/catchment-studies/assignments/${assignmentId}/surveys`, payload)
  return data
}
