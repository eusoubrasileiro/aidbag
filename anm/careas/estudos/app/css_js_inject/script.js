// to work on live-server vscode or chrome using a interferencia page downloaded
// add this bellow to testing page html
// <footer>  <!-- added by me for developing an injection tool -->    
// <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.6.4/jquery.min.js"></script>        
// <script src="script.js"></script>
// <link rel="stylesheet" href="style.css">  
// </footer> 

checked_dict = {}; // get dict of processes marked on database

$( document ).ready(function() {

  const header_html = `
    <div class="navbar">
        <div class="count-checkboxes-wrapper"> checkboxes
          total: <span id="count-checkboxes">0</span> 
          checked: <span id="count-checked-checkboxes">0</span>
        </div>
    </div>
  `;

  document.querySelector("body").insertAdjacentHTML("afterbegin", header_html);

  // to count number of of checkboxes checked and unchecked
  var $checkboxes = $("table#ctl00_cphConteudo_gvLowerRight tbody tr td input[type='checkbox']");
  var total = $checkboxes.length;
  $('#count-checkboxes').text(total);
    
  $checkboxes.change(function(){
    let countCheckedCheckboxes = $checkboxes.filter(':checked').length;
    $('#count-checked-checkboxes').text(countCheckedCheckboxes);
  });

  // Needs aidbag anm estudos work app running on localhost
  var mainprocess = $("table#ctl00_cphConteudo_gvLowerLeft tbody tr td:first-child")[0].innerText;
  console.log(`Process in analysis is ${mainprocess}`)
  fetch(`http://127.0.0.1:5000/get_prioridade?process=${mainprocess}`)
  .then(res => res.json()
  .then( data => { 
    checked_dict = data
    $("table#ctl00_cphConteudo_gvLowerRight tbody tr td label[onclick='IdentificarProcesso(this);']").each(
      function(i, element) { 
          let process = element.innerText;
          console.log(`${process} is ${checked_dict[process]}`);
          if(checked_dict[process] == '0') // style to red the ones to uncheck
            element.style.color = 'red';
      }
    );
    }))
    .catch((error) => {
      console.log(error);
    });
  
});




