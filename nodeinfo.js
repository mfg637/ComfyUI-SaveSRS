import { app } from "/scripts/app.js";
app.registerExtension(
	{
		name: "mfg637.save_srs",
		setup(app,file){
			async function read_srs(file){
				const reader = new FileReader();
				reader.readAsText(file);

				return new Promise((resolve, reject) => {
					reader.onloadend = function(){
						if (reader.error === null){
							if (reader.result.substring(0, 18) === '{"ftype": "CLSRS",'){
								resolve(JSON.parse(reader.result));
							}else{
								reject(new Error('Wrong file type'));
							}
						}else{
							reject(reader.error);
						}
					}
				});
			}

			const handleFile = app.handleFile;
			app.handleFile = async function(file) {
				if (file.type === ""){
					read_srs(file).then(function (result){
						app.loadGraphData(result.content.extra_pnginfo.workflow);
					}).catch(function (error){
						console.log("SRS loading error:", error.message)
					})
				} else {
					return handleFile.apply(this, arguments);
				}
			}
		},
	}
);
