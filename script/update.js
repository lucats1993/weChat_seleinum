
function formatDate(time,format='YY-MM-DD hh:mm:ss'){
    var date = new Date(time);

    var year = date.getFullYear(),
        month = date.getMonth()+1,//月份是从0开始的
        day = date.getDate(),
        hour = date.getHours(),
        min = date.getMinutes(),
        sec = date.getSeconds();
    var preArr = Array.apply(null,Array(10)).map(function(elem, index) {
        return '0'+index;
    });////开个长度为10的数组 格式为 00 01 02 03

    var newTime = format.replace(/YY/g,year)
                        .replace(/MM/g,preArr[month]||month)
                        .replace(/DD/g,preArr[day]||day)
                        .replace(/hh/g,preArr[hour]||hour)
                        .replace(/mm/g,preArr[min]||min)
                        .replace(/ss/g,preArr[sec]||sec);

    return newTime;         
}

function getCollection(path,col_name){
	conn = new Mongo(path);
	db = conn.getDB("weChat");
	col =db.getCollection(col_name)	
	return col
}

var progress_update_counts = 100;

var progress_update_seconds = 3;

function date2timestamp ( date ) {
  return Math.floor( date.getTime() / 1000 );

}

function timestamp2date ( timestamp ) {
  return new Date( timestamp * 1000 );

}

function now2timestamp ( ) {
  return date2timestamp( new Date() );

}

function createProgress ( total ) {
  return {
    start : now2timestamp(),
    timer : now2timestamp(),
    total : total,
    count : 0,
    pass : function () {
      if ( ( ++this.count % progress_update_counts == 0 ) && ( now2timestamp() - this.timer > progress_update_seconds ) ) {
        print( "\t" + this.count + ' / ' + this.total + "\t" + ( this.count / this.total * 100 ).toFixed( 2 ) + '%' );
        this.timer = now2timestamp();
      }
    },
    done : function () {
      print( "\t" + this.total + ' / ' + this.total + "\t100%\tCost " + ( now2timestamp() - this.start ) + ' seconds.' );
    }

  };

}


var col_name =formatDate(new Date().getTime(),"mediaYYMMDD")
local_col =getCollection("127.0.0.1:27017",col_name)	
server_col =getCollection("192.168.0.12:27017",col_name)	
var progress = createProgress( local_col.count() );
print( 'scan [ user ] for information...' );
local_col.find().forEach( function(m) {
	server_col.insert(m);
	progress.pass();

});
progress.done();
