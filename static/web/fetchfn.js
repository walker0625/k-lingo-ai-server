async function fetch_get(api){
    console.log(api);
    const result = await fetch(api).then(res => res.json());
    console.log(result)
    return result
}