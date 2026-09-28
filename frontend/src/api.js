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
